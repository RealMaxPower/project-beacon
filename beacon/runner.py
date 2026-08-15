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
    EVIDENCE_VERSION,
    Evidence,
    EventRecorder,
    Scenario,
    SubjectResult,
    canonical_digest,
    utc_now,
)
from beacon.secrets import REDACTION_NOTICE
from beacon.services import ToolRouter, build_service, is_service
from beacon.state import state_diff
from beacon.usage import REPORTED_NOTICE, UsageRecorder


REDACTED_EVIDENCE_FIELDS = (
    "scenario",
    "subject",
    "assertions",
    "state",
    "state_diff",
    "events",
    "artifacts",
    "usage",
)
"""
Every field of the bundle that can carry text the subject influenced.

Tool arguments and results, artifacts, the subject's stderr as it reaches
`subject.execution.error`, and the command line itself have all reached
evidence.json verbatim, so redaction runs over the whole document rather than
at each capture point.

`usage` is here because `UsageRecorder` stores a `target` per call - the agent
URL for an A2A subject, the server URL for an MCP one - and a credential passed
in a query string would otherwise survive in the one field the pass skipped.
"""

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
    router = ToolRouter(
        recorder,
        allowed=scenario.tools,
        max_tool_calls=scenario.limits.get("max_tool_calls"),
    )
    snapshots: dict[str, Any] = {}
    services: dict[str, Any] = {}
    # Whatever the scenario declares, in declaration order. A fixture with no
    # registered service is plain data - a pinned source document, say - not an
    # error, because a black-box scenario carries data it never serves.
    for name, fixture in scenario.fixtures.items():
        if not is_service(name):
            continue
        service = build_service(name, fixture, recorder)
        router.register(service)
        services[name] = service
        snapshots[name] = service.snapshot()
    # A black-box subject (an A2A agent, say) calls its own tools against the
    # real world and never touches Beacon's services, so a scenario for one
    # legitimately declares none. Its evidence is the response, not a state
    # diff; requiring a service here would only force a decorative fixture.
    if not services and scenario.tools:
        raise ValueError(
            "scenario scopes tools but defines no supported service fixture"
        )
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

    # Services are built before the directory exists, because building them is
    # the last thing that can reject the scenario outright. A scoped tool no
    # service provides is an authoring error, not a verdict - creating the run
    # directory first would leave an empty one behind for a run that never
    # started, and `--baseline-recent` reads that directory.
    recorder = EventRecorder()
    router, services, before = _build_services(scenario, recorder)

    run_dir.mkdir(parents=True, exist_ok=False)
    context = ExecutionContext(
        run_id=actual_run_id,
        run_dir=run_dir,
        scenario=scenario,
        tools=router,
        recorder=recorder,
        usage=UsageRecorder(
            max_calls=scenario.limits.get("max_subject_calls"),
            max_seconds=scenario.limits.get("max_subject_seconds"),
        ),
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
        # Reachable so an assertion can compare what the subject claimed
        # against the source the scenario pinned for it.
        "fixtures": scenario.fixtures,
        "usage": context.usage.summary(),
    }
    # Load-time validation should make this unreachable, but a run that dies
    # here dies after the subject has already done the work, discarding the
    # evidence for it. A Beacon-side failure is an INCOMPLETE to be recorded,
    # never an exception that loses the run.
    limitations = list(DEFAULT_LIMITATIONS) + list(context.limitations)
    # Said in the bundle, not only in the docstring of the module that stores
    # it. A reader who quotes a token count is reading the bundle, and the
    # caveat has to be where they are.
    if context.usage.reported:
        limitations.append(REPORTED_NOTICE)
    try:
        assertion_results = evaluate_all(
            scenario.assertions,
            evaluation_root,
            recorder.events,
        )
    except Exception as exc:
        recorder.record(
            "evaluator_error",
            scenario.id,
            {
                "error_type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        assertion_results = []
        limitations.append(
            "Beacon's evaluator failed on this run, so no assertion result is "
            f"available: {type(exc).__name__}: {exc}"
        )

    # An empty assertion set resolves to INCOMPLETE, which is the correct
    # answer whether the scenario declared none or the evaluator produced none.
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
    # Same rule as the evaluator above: the event log is built from what the
    # subject sent, and a bundle with no events still records the verdict,
    # the state diff and what went wrong. Losing the run instead would hand
    # a subject a way to erase the record of what it just did.
    try:
        events_payload = [event.to_dict() for event in recorder.events]
    except Exception as exc:
        events_payload = []
        limitations.append(
            "Beacon could not serialise this run's event log, so the bundle "
            f"records no events: {type(exc).__name__}: {exc}"
        )

    evidence = Evidence(
        evidence_version=EVIDENCE_VERSION,
        run_id=actual_run_id,
        started_at=started_at,
        completed_at=utc_now(),
        scenario=scenario.recorded_dict(),
        subject={
            **adapter.descriptor,
            "execution": subject_result.to_dict(),
        },
        result=result,
        assertions=[item.to_dict() for item in assertion_results],
        state=state_payload,
        state_diff=diff_payload,
        events=events_payload,
        artifacts=context.artifacts,
        usage=context.usage.summary(),
        reset_verified=reset_verified,
        limitations=limitations,
    )

    # Redact before finalize(), never inside write_evidence(): the digest must
    # be taken over the document that is actually published, or it will not
    # verify against the file on disk.
    secrets = context.secrets
    if secrets.active:
        for name in REDACTED_EVIDENCE_FIELDS:
            setattr(evidence, name, secrets.redact(getattr(evidence, name)))
        evidence.limitations.append(REDACTION_NOTICE)
        evidence.subject["secret_redaction"] = {
            "names": list(secrets.names),
            "replacements": secrets.redaction_count,
        }

    evidence.finalize()
    json_path, markdown_path = write_evidence(evidence, run_dir)

    (run_dir / "events.json").write_text(
        json.dumps(evidence.events, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return RunOutcome(evidence, json_path, markdown_path)

