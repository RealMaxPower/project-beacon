from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from beacon.determinism import compare_runs, run_signature
from beacon.models import Evidence, utc_now


BASELINE_VERSION = "0.1"

SUBJECT_IDENTITY_KEYS = ("id", "adapter", "agent_url", "server_url", "command")
"""
What makes two runs "the same subject under test".

`id` alone is nowhere near enough: every A2A subject reports id `a2a` and
every command subject reports `jsonl-command`, so filtering on it would
compare one agent's pass rate against a different agent's and report the
difference as a regression. What actually distinguishes them is the endpoint
or the command line, so those are included.

The cost is that changing a flag — a different model, a different temperature
— reads as a new subject and starts its history over. That is the right way
round: evidence is for one configuration, and losing history is recoverable
where a bogus comparison is not.

`name` is deliberately excluded. A hosted agent can rename itself between
releases without becoming a different subject.
"""


def subject_identity(subject: Mapping[str, Any]) -> str:
    """A stable, comparable key for a subject descriptor."""
    return json.dumps(
        {key: subject.get(key) for key in SUBJECT_IDENTITY_KEYS},
        sort_keys=True,
    )


@dataclass(frozen=True)
class Regression:
    kind: str
    assertion_id: str | None
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "assertion_id": self.assertion_id,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class BaselineComparison:
    """
    What changed since the recorded baseline.

    `--repeat` answers "does this subject agree with itself right now". That is
    a different question from "is this worse than it was last week", which is
    the one a builder actually asks before shipping. Both matter: a subject can
    be perfectly self-consistent and consistently wrong.
    """

    baseline_recorded_at: str
    baseline_runs: int
    current_runs: int
    regressions: tuple[Regression, ...]
    improvements: tuple[Regression, ...]
    source: str = "baseline"
    subject_changed: bool = False

    @property
    def regressed(self) -> bool:
        return bool(self.regressions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "baseline_recorded_at": self.baseline_recorded_at,
            "baseline_runs": self.baseline_runs,
            "current_runs": self.current_runs,
            "subject_changed": self.subject_changed,
            "regressions": [item.to_dict() for item in self.regressions],
            "improvements": [item.to_dict() for item in self.improvements],
        }

    def summary(self) -> str:
        lines = [
            f"Baseline ({self.source}): recorded {self.baseline_recorded_at} "
            f"over {self.baseline_runs} run(s)."
        ]
        if self.subject_changed:
            # Not a regression — a comparison that was never meaningful. Saying
            # "no change" here would be the worst available answer.
            lines.append(
                "  WARNING: this baseline was recorded against a different "
                "subject. The comparison below is not meaningful."
            )
        if not self.regressions and not self.improvements:
            lines.append("  No change against the baseline.")
        for item in self.regressions:
            lines.append(f"  REGRESSION  {item.detail}")
        for item in self.improvements:
            lines.append(f"  improved    {item.detail}")
        return "\n".join(lines)


Z_95 = 1.96
"""Two-sided 95% normal quantile, for the Wilson interval below."""


def wilson_interval(passed: int, total: int, z: float = Z_95) -> tuple[float, float]:
    """
    A confidence interval for a pass rate that behaves at small samples.

    This is what stops the comparison being a random number generator. An
    agent that genuinely passes a third of the time will fail a single run
    two times in three; comparing that raw 0% against a 33% baseline reports a
    regression on most runs, and a check that cries wolf in CI gets deleted
    within a week.

    Wilson rather than the textbook normal interval because the sample here is
    usually tiny and often all-pass or all-fail, where the normal
    approximation gives a zero-width interval and claims certainty it has not
    earned. Wilson stays sensible at n=1 and at p=0 or 1, which is the entire
    reason to prefer it.
    """
    if total <= 0:
        return (0.0, 1.0)
    observed = passed / total
    denominator = 1.0 + z * z / total
    centre = (observed + z * z / (2 * total)) / denominator
    spread = (z / denominator) * math.sqrt(
        observed * (1.0 - observed) / total + z * z / (4 * total * total)
    )
    return (max(0.0, centre - spread), min(1.0, centre + spread))


def _counts(evidences: Sequence[Evidence]) -> dict[str, tuple[int, int]]:
    """(passed, total) per assertion — the counts, not just the ratio."""
    totals: dict[str, list[bool]] = {}
    for evidence in evidences:
        for item in evidence.assertions:
            totals.setdefault(item["id"], []).append(bool(item["passed"]))
    return {
        assertion_id: (sum(results), len(results))
        for assertion_id, results in totals.items()
    }


def _rates(evidences: Sequence[Evidence]) -> dict[str, float]:
    """Pass rate per assertion, which is what survives an intermittent failure."""
    return {
        assertion_id: passed / total
        for assertion_id, (passed, total) in _counts(evidences).items()
    }


def build_baseline(evidences: Sequence[Evidence]) -> dict[str, Any]:
    if not evidences:
        raise ValueError("cannot record a baseline from zero runs")
    report = compare_runs(evidences)
    verdicts = report.verdicts
    return {
        "baseline_version": BASELINE_VERSION,
        "recorded_at": utc_now(),
        "scenario": evidences[0].scenario.get("id"),
        # Every identity key, present or not. Omitting an absent one would
        # make a stored baseline compare unequal to the very run it was built
        # from, because a missing key and a null key are not the same thing.
        "subject": {
            key: evidences[0].subject.get(key)
            for key in ("name",) + SUBJECT_IDENTITY_KEYS
        },
        "runs": len(evidences),
        "verdicts": verdicts,
        "dominant_verdict": report.dominant_verdict,
        "assertion_pass_rates": _rates(evidences),
        "state": {
            "before_digest": run_signature(evidences[0])["before_digest"],
            "after_digest": run_signature(evidences[0])["after_digest"],
        },
    }


def save_baseline(evidences: Sequence[Evidence], path: Path) -> dict[str, Any]:
    baseline = build_baseline(evidences)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return baseline


def load_baseline(path: Path) -> dict[str, Any]:
    baseline = json.loads(path.read_text(encoding="utf-8"))
    if baseline.get("baseline_version") != BASELINE_VERSION:
        raise ValueError(
            f"unsupported baseline version: {baseline.get('baseline_version')}"
        )
    return baseline


def load_recent_evidence(
    output_dir: Path,
    *,
    like: Evidence | None = None,
    exclude_run_ids: Sequence[str] = (),
    limit: int = 10,
) -> list[Evidence]:
    """
    The most recent prior runs already on disk, oldest first.

    The committed-file baseline asks "is this worse than the version we
    blessed". This asks "is this worse than yesterday", which is the only
    question available when nobody has blessed anything yet — and it needs no
    file to maintain, because every run already writes an evidence bundle.

    Runs of a different scenario or a different subject are skipped rather than
    compared. A shared output directory is the normal case, and silently
    measuring one agent against another would be worse than not comparing at
    all.
    """
    if limit <= 0:
        return []
    excluded = set(exclude_run_ids)
    scenario_id = like.scenario.get("id") if like is not None else None
    identity = subject_identity(like.subject) if like is not None else None

    found: list[Evidence] = []
    for path in sorted(output_dir.glob("*/evidence.json")):
        try:
            evidence = Evidence.load(path)
        except (OSError, ValueError, json.JSONDecodeError):
            # A half-written or hand-edited bundle should not break a run that
            # is otherwise fine. It just does not count as history.
            continue
        if evidence.run_id in excluded:
            continue
        if scenario_id is not None and evidence.scenario.get("id") != scenario_id:
            continue
        if identity is not None and subject_identity(evidence.subject) != identity:
            continue
        found.append(evidence)

    # started_at is ISO-8601 UTC, so lexical order is chronological. run_id
    # breaks ties, which matters because a fast repeat can share a timestamp.
    found.sort(key=lambda evidence: (evidence.started_at, evidence.run_id))
    return found[-limit:]


def compare_to_baseline(
    evidences: Sequence[Evidence],
    baseline: dict[str, Any],
    *,
    tolerance: float = 0.0,
    source: str = "baseline",
) -> BaselineComparison:
    """
    Compare this run against the recorded one, by pass *rate*.

    Rates rather than verdicts, because a subject that fails one run in five
    passes any single comparison four times out of five. Comparing rates is
    what makes an intermittent regression visible at all.

    A drop is only called a regression when this run's sample is small enough
    to rule out chance — specifically when the upper end of the current pass
    rate's confidence interval is still below the baseline. This is what makes
    the check usable in CI: an agent that truly passes a third of the time
    fails a single run two times in three, and reporting each of those as a
    regression would make the signal worthless. It also means a single run is
    still enough to catch a subject that was reliable and is now broken —
    how many runs it takes to prove a regression scales with how flaky the
    baseline already said the subject was.

    The uncertainty in the *baseline's* own rate is not modelled; a baseline
    recorded from very few runs is a weak claim regardless of the arithmetic,
    which is why the run count is printed alongside it.

    `tolerance` is a separate, deliberate margin on top: with 0.1, a ten-point
    drop is accepted as uninteresting even if it is statistically real.
    """
    counts = _counts(evidences)
    recorded = baseline.get("assertion_pass_rates", {})
    regressions: list[Regression] = []
    improvements: list[Regression] = []

    for assertion_id, was in sorted(recorded.items()):
        if assertion_id not in counts:
            regressions.append(
                Regression(
                    "assertion_missing",
                    assertion_id,
                    f"{assertion_id} is in the baseline but not in this run",
                )
            )
            continue
        passed, total = counts[assertion_id]
        now = passed / total
        low, high = wilson_interval(passed, total)
        detail = (
            f"{assertion_id} passed {was:.0%} of baseline runs, "
            f"{now:.0%} now ({passed}/{total})"
        )
        if high < was - tolerance:
            regressions.append(Regression("pass_rate_dropped", assertion_id, detail))
        elif low > was + tolerance:
            improvements.append(Regression("pass_rate_rose", assertion_id, detail))

    for assertion_id in sorted(set(counts) - set(recorded)):
        improvements.append(
            Regression(
                "assertion_added",
                assertion_id,
                f"{assertion_id} is new since the baseline",
            )
        )

    recorded_subject = baseline.get("subject")
    subject_changed = bool(
        evidences
        and isinstance(recorded_subject, dict)
        and subject_identity(recorded_subject) != subject_identity(evidences[0].subject)
    )

    return BaselineComparison(
        baseline_recorded_at=baseline.get("recorded_at", "unknown"),
        baseline_runs=int(baseline.get("runs", 0)),
        current_runs=len(evidences),
        regressions=tuple(regressions),
        improvements=tuple(improvements),
        source=source,
        subject_changed=subject_changed,
    )
