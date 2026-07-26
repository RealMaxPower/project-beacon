from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from beacon.models import Evidence


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
        "before_digest": evidence.state["before_digest"],
        "after_digest": evidence.state["after_digest"],
        "reset_verified": evidence.reset_verified,
        "assertions": [
            {"id": item["id"], "passed": item["passed"]}
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
class DeterminismReport:
    stable: bool
    run_count: int
    signature: dict[str, Any]
    divergent_fields: tuple[str, ...]
    tool_sequences_differ: bool

    def summary(self) -> str:
        lines: list[str] = []
        if self.stable:
            lines.append(
                f"Determinism: STABLE across {self.run_count} runs "
                f"(state digests, verdict, and assertion results identical)."
            )
        else:
            lines.append(
                f"Determinism: DIVERGENT across {self.run_count} runs."
            )
            for field in self.divergent_fields:
                lines.append(f"  differs: {field}")
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

    sequences = {tool_sequence(evidence) for evidence in evidences}
    return DeterminismReport(
        stable=not divergent,
        run_count=len(evidences),
        signature=baseline,
        divergent_fields=tuple(divergent),
        tool_sequences_differ=len(sequences) > 1,
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
