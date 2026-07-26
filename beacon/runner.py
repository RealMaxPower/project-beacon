from __future__ import annotations

import json
import traceback
import uuid
from pathlib import Path
from typing import Any

from beacon.adapters.base import ExecutionContext, SubjectAdapter
from beacon.evaluation import evaluate_all, resolve_result
from beacon.evidence import write_evidence
from beacon.models import (
    Evidence,
    EventRecorder,
    Scenario,
    SubjectResult,
    canonical_digest,
    utc_now,
)
from beacon.services import MailService, ToolRouter
from beacon.state import state_diff


DEFAULT_LIMITATIONS = [
    "This run evaluates behavior in a synthetic environment; it is not a safety certification.",
    "The MVP command adapter uses process and working-directory isolation, not a hardened container or VM boundary.",
    "Black-box and protocol-level evidence cannot reveal private model reasoning or undeclared internal operations.",
]


class RunOutcome:
    def __init__(
        self,
        evidence: Evidence,
        json_path: Path,
        markdown_path: Path,
    ) -> None:
        self.evidence = evidence
        self.json_path = json_path
        self.markdown_path = markdown_path


def _build_services(
    scenario: Scenario,
    recorder: EventRecorder,
) -> tuple[ToolRouter, dict[str, Any], dict[str, Any]]:
    router = ToolRouter(recorder, allowed=scenario.tools)
    snapshots: dict[str, Any] = {}
    services: dict[str, Any] = {}
    if "mail" in scenario.fixtures:
        mail = MailService(scenario.fixtures["mail"], recorder)
        router.register(mail)
        services["mail"] = mail
        snapshots["mail"] = mail.snapshot()
    if not services:
        raise ValueError("scenario must define at least one supported service fixture")
    unknown = router.unknown_tools()
    if unknown:
        raise ValueError(
            "scenario scopes tools no service provides: " + ", ".join(unknown)
        )
    return router, services, snapshots


def run_scenario(
    scenario: Scenario,
    adapter: SubjectAdapter,
    *,
    output_dir: str | Path,
    run_id: str | None = None,
) -> RunOutcome:
    actual_run_id = run_id or f"run-{uuid.uuid4().hex[:12]}"
    run_dir = Path(output_dir).resolve() / actual_run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    recorder = EventRecorder()
    router, services, before = _build_services(scenario, recorder)
    context = ExecutionContext(
        run_id=actual_run_id,
        run_dir=run_dir,
        scenario=scenario,
        tools=router,
        recorder=recorder,
    )
    started_at = utc_now()
    subject_result: SubjectResult
    try:
        subject_result = adapter.execute(context)
    except Exception as exc:
        recorder.record(
            "subject_error",
            adapter.descriptor.get("id", "unknown-subject"),
            {
                "error_type": type(exc).__name__,
                "message": str(exc),
            },
        )
        subject_result = SubjectResult(
            status="error",
            error=f"{type(exc).__name__}: {exc}",
            metadata={"traceback": traceback.format_exc()},
        )

    # A declared artifact that never arrived means Beacon has nothing to grade,
    # not that the subject behaved badly. Assertions reading that artifact
    # would report FAIL, which reads as a verdict on the subject; the honest
    # answer is that evidence collection did not succeed.
    required_artifact = scenario.required_artifact
    if (
        subject_result.status == "completed"
        and required_artifact
        and required_artifact not in context.artifacts
    ):
        recorder.record(
            "output_contract_unmet",
            adapter.descriptor.get("id", "unknown-subject"),
            {
                "required_artifact": required_artifact,
                "artifacts_received": sorted(context.artifacts),
            },
        )
        subject_result.status = "evidence_missing"
        subject_result.error = (
            f"subject completed without the required artifact: {required_artifact}"
        )

    after = {name: service.snapshot() for name, service in services.items()}
    evaluation_root = {
        "before": before,
        "after": after,
        "artifacts": context.artifacts,
        "subject": subject_result.to_dict(),
    }
    assertion_results = evaluate_all(
        scenario.assertions,
        evaluation_root,
        recorder.events,
    )
    result = resolve_result(subject_result.status, assertion_results)

    reset_verified = True
    for name, service in services.items():
        service.reset()
        reset_verified = reset_verified and (
            canonical_digest(service.snapshot()) == canonical_digest(before[name])
        )

    changes = state_diff(before, after)
    state_payload = {
        "before_digest": canonical_digest(before),
        "after_digest": canonical_digest(after),
        "before": before,
        "after": after,
    }
    diff_payload = {
        "change_count": len(changes),
        "changes": changes,
    }
    evidence = Evidence(
        evidence_version="0.1",
        run_id=actual_run_id,
        started_at=started_at,
        completed_at=utc_now(),
        scenario=scenario.public_dict(),
        subject={
            **adapter.descriptor,
            "execution": subject_result.to_dict(),
        },
        result=result,
        assertions=[item.to_dict() for item in assertion_results],
        state=state_payload,
        state_diff=diff_payload,
        events=[event.to_dict() for event in recorder.events],
        artifacts=context.artifacts,
        reset_verified=reset_verified,
        limitations=list(DEFAULT_LIMITATIONS),
    )
    evidence.finalize()
    json_path, markdown_path = write_evidence(evidence, run_dir)

    (run_dir / "events.json").write_text(
        json.dumps(evidence.events, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return RunOutcome(evidence, json_path, markdown_path)

