from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from beacon.determinism import compare_runs, run_signature
from beacon.models import Evidence, utc_now


BASELINE_VERSION = "0.1"


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

    @property
    def regressed(self) -> bool:
        return bool(self.regressions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_recorded_at": self.baseline_recorded_at,
            "baseline_runs": self.baseline_runs,
            "current_runs": self.current_runs,
            "regressions": [item.to_dict() for item in self.regressions],
            "improvements": [item.to_dict() for item in self.improvements],
        }

    def summary(self) -> str:
        lines = [
            f"Baseline: recorded {self.baseline_recorded_at} "
            f"over {self.baseline_runs} run(s)."
        ]
        if not self.regressions and not self.improvements:
            lines.append("  No change against the baseline.")
        for item in self.regressions:
            lines.append(f"  REGRESSION  {item.detail}")
        for item in self.improvements:
            lines.append(f"  improved    {item.detail}")
        return "\n".join(lines)


def _rates(evidences: Sequence[Evidence]) -> dict[str, float]:
    """Pass rate per assertion, which is what survives an intermittent failure."""
    totals: dict[str, list[bool]] = {}
    for evidence in evidences:
        for item in evidence.assertions:
            totals.setdefault(item["id"], []).append(bool(item["passed"]))
    return {
        assertion_id: sum(results) / len(results)
        for assertion_id, results in totals.items()
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
        "subject": {
            key: evidences[0].subject.get(key)
            for key in ("id", "name", "adapter", "agent_url", "server_url")
            if evidences[0].subject.get(key) is not None
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


def compare_to_baseline(
    evidences: Sequence[Evidence],
    baseline: dict[str, Any],
    *,
    tolerance: float = 0.0,
) -> BaselineComparison:
    """
    Compare this run against the recorded one, by pass *rate*.

    Rates rather than verdicts, because a subject that fails one run in five
    passes any single comparison four times out of five. Comparing rates is
    what makes an intermittent regression visible at all.

    `tolerance` allows for sampling noise: with a handful of runs, a rate can
    move a little without meaning anything. It defaults to zero so that any
    drop is reported, and a caller who knows their subject is noisy can raise
    it deliberately.
    """
    current = _rates(evidences)
    recorded = baseline.get("assertion_pass_rates", {})
    regressions: list[Regression] = []
    improvements: list[Regression] = []

    for assertion_id, was in sorted(recorded.items()):
        if assertion_id not in current:
            regressions.append(
                Regression(
                    "assertion_missing",
                    assertion_id,
                    f"{assertion_id} is in the baseline but not in this run",
                )
            )
            continue
        now = current[assertion_id]
        if now < was - tolerance:
            regressions.append(
                Regression(
                    "pass_rate_dropped",
                    assertion_id,
                    f"{assertion_id} passed {was:.0%} of baseline runs, "
                    f"{now:.0%} now",
                )
            )
        elif now > was + tolerance:
            improvements.append(
                Regression(
                    "pass_rate_rose",
                    assertion_id,
                    f"{assertion_id} passed {was:.0%} of baseline runs, "
                    f"{now:.0%} now",
                )
            )

    for assertion_id in sorted(set(current) - set(recorded)):
        improvements.append(
            Regression(
                "assertion_added",
                assertion_id,
                f"{assertion_id} is new since the baseline",
            )
        )

    return BaselineComparison(
        baseline_recorded_at=baseline.get("recorded_at", "unknown"),
        baseline_runs=int(baseline.get("runs", 0)),
        current_runs=len(evidences),
        regressions=tuple(regressions),
        improvements=tuple(improvements),
    )
