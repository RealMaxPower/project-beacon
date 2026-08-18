from __future__ import annotations

import dataclasses
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


UNREDACTED_EVIDENCE_FIELDS = frozenset(
    {
        "evidence_version",
        "run_id",
        "started_at",
        "completed_at",
        "result",
        "reset_verified",
        "digest",
    }
)
"""
The fields the harness writes itself, which no subject can put text into.

This list is inverted on purpose, and the inversion is the fix for a real leak.
It used to name the fields to redact, its docstring claimed to cover "every
field of the bundle that can carry text the subject influenced", and it did
not: `repeat` carries a full `artifacts` and `subject` for each additional
pass, and was never added. A run with `--env-secret` redacted the key from
pass 1 and published it in full from pass 2, while `subject.secret_redaction`
reported a count of replacements - a bundle asserting a property it did not
have, which is worse than no redaction because §7 tells readers to trust it.

An allowlist of things to protect fails silently every time someone adds a
field and forgets. An allowlist of things that need no protection fails loudly:
a new field is redacted by default, and `test_secret_redaction.py` asserts that
these two sets account for every field of `Evidence`, so a field that is
neither is a test failure rather than a leak.

`digest` is here because it is computed in `finalize()` from the redacted
document; redacting it would hash something that was never published.

Everything else is a container the subject reaches: tool arguments and results,
artifacts, the subject's stderr as it lands in `subject.execution.error`, the
command line, and `usage`, which stores a per-call `target` - the agent URL for
an A2A subject, the server URL for an MCP one - where a credential in a query
string would otherwise survive.
"""


def redacted_evidence_fields() -> tuple[str, ...]:
    """Every `Evidence` field that is not harness-generated, in declared order."""
    return tuple(
        field.name
        for field in dataclasses.fields(Evidence)
        if field.name not in UNREDACTED_EVIDENCE_FIELDS
    )


def redact_evidence(evidence: Evidence, secrets: Any) -> None:
    """
    Remove every registered secret from the bundle, in place.

    A function rather than a loop inside `run_scenario` so that a test can hand
    it a bundle with a secret planted in every field and check that none
    survives. While this lived inline, the only way to exercise it was a full
    run, so the one field it skipped was the one nobody thought to run.
    """
    if not secrets.active:
        return
    for name in redacted_evidence_fields():
        setattr(evidence, name, secrets.redact(getattr(evidence, name)))
    # Appended after the pass, so the notice itself is never scanned. It
    # contains no subject text, and redacting it would only cost a walk.
    evidence.limitations.append(REDACTION_NOTICE)
    evidence.subject["secret_redaction"] = {
        "names": list(secrets.names),
        "replacements": secrets.redaction_count,
    }

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


def _repeat_passes(
    scenario: Scenario,
    adapter: SubjectAdapter,
    run_dir: Path,
    first_recorder: EventRecorder,
) -> list[dict[str, Any]]:
    """
    Run the subject again on the same input, for a scenario that asked.

    One question needs this and no other: whether the shape of the answer is a
    property of the contract or of the run. A single pass cannot show it — the
    output was whatever it was — and comparing two separate `beacon run`
    invocations grades the operator's diligence rather than the agent.

    Everything the second pass touches is fresh: its own services from the same
    fixture, its own recorder, its own directory. Nothing carries over, so the
    subject is answering the same question rather than a question about what it
    did last time.

    What comes back is deliberately thin — artifacts, end state, ending. The
    first pass keeps the events and the state diff, so every existing assertion
    still reads exactly one run and nothing double-counts. A failure in a later
    pass is recorded and not raised: the subject has already done the work
    once, and losing the run would cost more than the comparison is worth.
    """
    if scenario.repeat <= 1:
        return []
    passes: list[dict[str, Any]] = []
    for index in range(2, scenario.repeat + 1):
        recorder = EventRecorder()
        router, services, _ = _build_services(scenario, recorder)
        pass_dir = run_dir / f"repeat-{index}"
        pass_dir.mkdir(parents=True, exist_ok=False)
        context = ExecutionContext(
            run_id=f"{run_dir.name}-repeat-{index}",
            run_dir=pass_dir,
            scenario=scenario,
            tools=router,
            recorder=recorder,
            usage=UsageRecorder(
                max_calls=scenario.limits.get("max_subject_calls"),
                max_seconds=scenario.limits.get("max_subject_seconds"),
            ),
        )
        try:
            result = adapter.execute(context)
        except Exception as exc:
            first_recorder.record(
                "repeat_pass_failed",
                scenario.id,
                {"pass": index, "error_type": type(exc).__name__, "message": str(exc)},
            )
            continue
        passes.append(
            {
                "pass": index,
                "artifacts": context.artifacts,
                "after": {
                    name: service.snapshot() for name, service in services.items()
                },
                "subject": result.to_dict(),
            }
        )
    return passes


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

    repeats = _repeat_passes(scenario, adapter, run_dir, recorder)

    evaluation_root = {
        "before": before,
        "after": after,
        "artifacts": context.artifacts,
        "subject": subject_result.to_dict(),
        # Reachable so an assertion can compare what the subject claimed
        # against the source the scenario pinned for it.
        "fixtures": scenario.fixtures,
        "usage": context.usage.summary(),
        # Empty unless the scenario declared `repeat`. A list rather than a
        # single entry so an assertion comparing passes does not have to care
        # how many there were.
        "repeat": repeats,
        # How many were *asked* for, which the list above cannot show once a
        # pass has died. Evaluation-only: it is not a field of the bundle, and
        # the count a reader needs is already in `scenario`.
        "repeat_declared": scenario.repeat,
    }
    # Load-time validation should make this unreachable, but a run that dies
    # here dies after the subject has already done the work, discarding the
    # evidence for it. A Beacon-side failure is an INCOMPLETE to be recorded,
    # never an exception that loses the run.
    limitations = list(DEFAULT_LIMITATIONS) + list(context.limitations)
    # A pass that died was recorded as an event and read by nothing, so a
    # bundle from a run that lost one looked exactly like a bundle from a run
    # that did not. The event is the record; this is the sentence a reader gets.
    lost = [
        event.payload.get("pass")
        for event in recorder.events
        if event.kind == "repeat_pass_failed"
    ]
    if lost:
        limitations.append(
            f"{len(lost)} of the {scenario.repeat - 1} additional pass(es) this "
            f"scenario declared did not run (pass "
            f"{', '.join(str(number) for number in lost)}). Any comparison "
            f"across passes was made over fewer runs than were asked for."
        )
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
        repeat=repeats,
        reset_verified=reset_verified,
        limitations=limitations,
    )

    # Redact before finalize(), never inside write_evidence(): the digest must
    # be taken over the document that is actually published, or it will not
    # verify against the file on disk.
    redact_evidence(evidence, context.secrets)

    evidence.finalize()
    json_path, markdown_path = write_evidence(evidence, run_dir)

    (run_dir / "events.json").write_text(
        json.dumps(evidence.events, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return RunOutcome(evidence, json_path, markdown_path)

