from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from beacon.models import Evidence, canonical_digest


TEXT_PLACEHOLDER = "<beacon:text>"
EMPTY_TEXT_PLACEHOLDER = "<beacon:empty-text>"


def state_shape(value: Any) -> Any:
    """
    A service snapshot with its free text collapsed, for comparing repeats.

    The exact state digest answers "is this byte-for-byte what it was", which
    is the right question for tamper evidence and the wrong one for asking
    whether a subject behaved the same way twice. A model that drafts a reply
    writes different words every run, so an exact comparison reports every
    model-backed subject as non-deterministic however correct it is — the same
    false positive that artifact wording was already excluded to avoid, reached
    through state instead.

    So structure and non-text values are kept and string *contents* dropped:
    a different number of drafts, a renamed or missing key, a changed count or
    flag, a body that is sometimes empty — all still diverge. Only the prose
    stops mattering.

    This does not weaken the check as much as it looks. What a scenario cares
    about in its state is what its assertions read, and assertion results are
    compared separately and exactly. This is the supplementary tripwire, not
    the graded property. A string-only difference is still reported, so nothing
    is dropped silently.
    """
    if isinstance(value, dict):
        return {key: state_shape(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [state_shape(item) for item in value]
    if isinstance(value, str):
        return TEXT_PLACEHOLDER if value else EMPTY_TEXT_PLACEHOLDER
    return value


VOLATILE_EVIDENCE_FIELDS = (
    "run_id",
    "started_at",
    "completed_at",
    "digest",
    "events",
    "artifacts",
)
"""
Fields that legitimately differ between two identical runs.

`digest` covers the whole document including the timestamps and the run id, so
it can never be equal across runs and is not a determinism signal. Event
timestamps move for the same reason. Artifact *content* is excluded because a
model-backed subject rewrites its prose every run without that being a defect;
artifact *names* are part of the signature instead.
"""


def run_signature(evidence: Evidence) -> dict[str, Any]:
    """Reduce a run to the parts that must be identical across repeats."""
    return {
        "result": evidence.result,
        "before_state": canonical_digest(state_shape(evidence.state["before"])),
        "after_state": canonical_digest(state_shape(evidence.state["after"])),
        "reset_verified": evidence.reset_verified,
        # `measured` belongs here as much as `passed` does. Without it, an
        # assertion Beacon observed failing and one it could not evaluate at all
        # both serialise as `passed: False`, so a run that found a real defect
        # and a run that could read nothing produce identical signatures and the
        # report says STABLE. That erases the exact distinction the rest of this
        # project treats as load-bearing, in the report whose job is to say
        # whether a subject is reproducible.
        "assertions": [
            {
                "id": item["id"],
                "passed": item["passed"],
                "measured": item.get("measured", True),
            }
            for item in evidence.assertions
        ],
        "artifact_names": sorted(evidence.artifacts),
    }


def tool_sequence(evidence: Evidence) -> tuple[str, ...]:
    """The ordered tool names a subject called, for informational comparison."""
    return tuple(
        event["target"]
        for event in evidence.events
        if event["kind"] == "tool_call"
    )


@dataclass(frozen=True)
class FlakyAssertion:
    """One assertion that did not agree with itself across repeats."""

    id: str
    passed: int
    total: int
    failed_runs: tuple[str, ...]

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "passed": self.passed,
            "total": self.total,
            "pass_rate": round(self.pass_rate, 3),
            "failed_runs": list(self.failed_runs),
        }


@dataclass(frozen=True)
class DeterminismReport:
    stable: bool
    run_count: int
    signature: dict[str, Any]
    divergent_fields: tuple[str, ...]
    tool_sequences_differ: bool
    verdicts: dict[str, int] = field(default_factory=dict)
    flaky: tuple[FlakyAssertion, ...] = ()
    state_text_differs: bool = False
    """
    The state matched in shape but not in wording.

    Reported rather than merely tolerated: it is the normal signature of a
    model-backed subject, and it is also what a scenario grading prose through
    an assertion would want to know about.
    """

    @property
    def dominant_verdict(self) -> str | None:
        if not self.verdicts:
            return None
        return max(self.verdicts.items(), key=lambda item: item[1])[0]

    def to_dict(self) -> dict[str, Any]:
        return {
            "stable": self.stable,
            "run_count": self.run_count,
            "verdicts": dict(self.verdicts),
            "divergent_fields": list(self.divergent_fields),
            "flaky": [item.to_dict() for item in self.flaky],
            "state_text_differs": self.state_text_differs,
        }

    def summary(self) -> str:
        """
        Report a rate, not just a yes or no.

        "DIVERGENT" tells you something moved. It does not tell you whether the
        subject fails one run in twenty or nineteen, or which assertion is
        responsible — and those are the only two facts that let someone decide
        whether to ship. An intermittent failure looks like a pass most of the
        time, so the count is the finding.
        """
        lines: list[str] = []
        if self.stable:
            lines.append(
                f"Determinism: STABLE across {self.run_count} runs "
                f"(state shape, verdict, and assertion results identical)."
            )
        else:
            lines.append(f"Determinism: DIVERGENT across {self.run_count} runs.")

        if len(self.verdicts) > 1:
            parts = [
                f"{verdict} {count} ({count / self.run_count:.0%})"
                for verdict, count in sorted(
                    self.verdicts.items(), key=lambda item: -item[1]
                )
            ]
            lines.append(f"  verdicts: {', '.join(parts)}")

        for item in self.flaky:
            shown = ", ".join(item.failed_runs[:4])
            more = "" if len(item.failed_runs) <= 4 else f", +{len(item.failed_runs) - 4} more"
            lines.append(
                f"  flaky: {item.id} passed {item.passed}/{item.total} "
                f"({item.pass_rate:.0%}) — failed on {shown}{more}"
            )

        for field_name in self.divergent_fields:
            if field_name != "assertions":
                lines.append(f"  differs: {field_name}")

        if self.state_text_differs:
            lines.append(
                "  note: the state matched in shape but the text within it "
                "differed. Expected of a model-backed subject that writes "
                "prose; the wording itself is graded by assertions, not here."
            )

        if self.tool_sequences_differ:
            lines.append(
                "  note: tool-call order varied between runs. This does not "
                "affect the verdict and is expected of a model-backed subject."
            )
        return "\n".join(lines)


def compare_runs(evidences: Sequence[Evidence]) -> DeterminismReport:
    """Compare repeated runs of one scenario against the same subject."""
    if not evidences:
        raise ValueError("cannot compare an empty set of runs")

    signatures = [run_signature(evidence) for evidence in evidences]
    baseline = signatures[0]
    divergent: list[str] = []
    for key in baseline:
        if any(signature[key] != baseline[key] for signature in signatures[1:]):
            divergent.append(key)

    verdicts: dict[str, int] = {}
    for evidence in evidences:
        verdicts[evidence.result] = verdicts.get(evidence.result, 0) + 1

    # Which assertion is responsible, and how often. An assertion that passes
    # every run is not interesting; one that passes most runs is the dangerous
    # kind, because any single run is likely to look fine.
    # Only measured outcomes, for the same reason `measured` is in the
    # signature: a run Beacon could not evaluate is not evidence that the
    # assertion failed, and folding it in as a failure invents flakiness out of
    # an infrastructure fault.
    outcomes: dict[str, list[bool]] = {}
    failed_runs: dict[str, list[str]] = {}
    for evidence in evidences:
        for item in evidence.assertions:
            if not item.get("measured", True):
                continue
            outcomes.setdefault(item["id"], []).append(bool(item["passed"]))
            if not item["passed"]:
                failed_runs.setdefault(item["id"], []).append(evidence.run_id)
    flaky = tuple(
        FlakyAssertion(
            id=assertion_id,
            passed=sum(results),
            total=len(results),
            failed_runs=tuple(failed_runs.get(assertion_id, ())),
        )
        for assertion_id, results in outcomes.items()
        if 0 < sum(results) < len(results)
    )

    # Shape-equal but not byte-equal: the wording moved and nothing else did.
    # Worth saying out loud rather than passing over in silence.
    exact_states = {
        (evidence.state["before_digest"], evidence.state["after_digest"])
        for evidence in evidences
    }
    state_text_differs = len(exact_states) > 1 and not (
        {"before_state", "after_state"} & set(divergent)
    )

    sequences = {tool_sequence(evidence) for evidence in evidences}
    return DeterminismReport(
        stable=not divergent,
        run_count=len(evidences),
        signature=baseline,
        divergent_fields=tuple(divergent),
        tool_sequences_differ=len(sequences) > 1,
        verdicts=verdicts,
        flaky=flaky,
        state_text_differs=state_text_differs,
    )


def repeat_run_ids(base: str | None, count: int) -> Iterable[str | None]:
    """Yield one run id per repeat, keeping a caller-supplied id readable."""
    for index in range(1, count + 1):
        if base is None:
            yield None
        elif count == 1:
            yield base
        else:
            yield f"{base}-{index:03d}"
