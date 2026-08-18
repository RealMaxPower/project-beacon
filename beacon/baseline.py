from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from beacon.determinism import compare_runs
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


#: Stands in for the directory part of any absolute path on the command line.
#:
#: `site/tools/build_fixtures.py` learned this the expensive way and uses
#: `<repo>` and `<python>` for the same reason: the machine that recorded
#: something must not be identifiable from it, and 32 committed fixtures once
#: shipped a laptop's absolute interpreter path. This is the same scrub one
#: layer down, where it also buys correctness rather than only privacy.
PATH_PLACEHOLDER = "<path>"


def portable_command(command: Any) -> Any:
    """
    The command line with the recording machine taken out of it.

    A baseline is meant to be committed and compared against from anywhere, and
    `subject_identity` hashes the whole argv. The adapter resolves a subject to
    absolute paths, so a baseline recorded in one checkout carried
    `/tmp/pv/bin/python` and `/tmp/sd/project_beacon-0.1.2/examples/agent.py`,
    and comparing from any other directory produced "this baseline was recorded
    against a different subject. The comparison below is not meaningful" —
    which is every use `baselines/` exists for. The committed
    `inbox-briefing.reference.json` escaped only because the in-process adapter
    records `command: null`.

    Only the directory goes. The basename and every other argument stay,
    because those are what distinguish one subject from another: five baselines
    across a model ladder share a `name`, an `id` and an `adapter`, and differ
    solely in `--model`. Scrubbing the whole command would make them one
    subject with five contradictory histories, which is worse than the problem.
    """
    if not isinstance(command, (list, tuple)):
        return command
    scrubbed = []
    for token in command:
        text = str(token)
        # A path, not a flag, a URL, or a bare word. The second separator is
        # what tells `/tmp/pv/bin/python` from an argument that merely starts
        # with a slash, and the drive letter covers Windows.
        looks_absolute = (text.startswith("/") and text.count("/") >= 2) or (
            len(text) > 3 and text[1] == ":" and text[2] in "\\/"
        )
        if looks_absolute:
            base = text.replace("\\", "/").rsplit("/", 1)[-1]
            scrubbed.append(f"{PATH_PLACEHOLDER}/{base}" if base else text)
        else:
            scrubbed.append(text)
    return scrubbed


def subject_identity(subject: Mapping[str, Any]) -> str:
    """
    A stable, comparable key for a subject descriptor.

    Stable across machines, not only across runs on one. The command is
    normalised here rather than at the call sites so that a baseline recorded
    before this existed still compares equal to a run of the same subject
    today: both sides go through the same scrub.
    """
    identity = {key: subject.get(key) for key in SUBJECT_IDENTITY_KEYS}
    identity["command"] = portable_command(identity.get("command"))
    return json.dumps(identity, sort_keys=True)


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
    """
    (passed, total) per assertion — the counts, not just the ratio.

    Unmeasured assertions leave the denominator entirely. They used to be folded
    in as failures, which is how a crashed run came to be reported as the agent
    getting worse: a model server killed mid-run produced INCOMPLETE with
    `passed=False measured=False`, `_counts` read only `passed`, and the
    comparison announced "task-completed passed 100% of baseline runs, 0% now
    (0/1)". CI then exited non-zero and blamed the agent for an infrastructure
    fault.

    A gap is not a regression. `compare_to_baseline` reports it as its own kind
    so it stays visible rather than being silently dropped.
    """
    totals: dict[str, list[bool]] = {}
    for evidence in evidences:
        for item in evidence.assertions:
            if not item.get("measured", True):
                continue
            totals.setdefault(item["id"], []).append(bool(item["passed"]))
    return {
        assertion_id: (sum(results), len(results))
        for assertion_id, results in totals.items()
    }


def _unmeasured(evidences: Sequence[Evidence]) -> dict[str, int]:
    """How many runs could not evaluate each assertion at all."""
    gaps: dict[str, int] = {}
    for evidence in evidences:
        for item in evidence.assertions:
            if not item.get("measured", True):
                gaps[item["id"]] = gaps.get(item["id"], 0) + 1
    return gaps


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
        #
        # The command is stored scrubbed as well as compared scrubbed. A
        # baseline is a file people commit, and writing an absolute path into
        # one publishes the recording machine's directory layout to everyone
        # who clones the repository.
        "subject": {
            **{
                key: evidences[0].subject.get(key)
                for key in ("name",) + SUBJECT_IDENTITY_KEYS
            },
            "command": portable_command(evidences[0].subject.get("command")),
        },
        "runs": len(evidences),
        "verdicts": verdicts,
        "dominant_verdict": report.dominant_verdict,
        "assertion_pass_rates": _rates(evidences),
        # The exact digests, read from the evidence rather than through
        # `run_signature`, which compares state by shape so that a rephrasing
        # subject is not called non-deterministic. A baseline records what the
        # state actually was; it does not compare it.
        "state": {
            "before_digest": evidences[0].state["before_digest"],
            "after_digest": evidences[0].state["after_digest"],
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
            #
            # `Evidence.from_dict` raises ValueError for everything it cannot
            # read — unknown fields, missing required ones, a document that is
            # not an object at all — so this tuple is that whole contract, not
            # a list of the failures someone happened to hit. JSONDecodeError
            # is a ValueError subclass and is named only as documentation of
            # the common case.
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
    gaps = _unmeasured(evidences)
    recorded = baseline.get("assertion_pass_rates", {})
    regressions: list[Regression] = []
    improvements: list[Regression] = []

    for assertion_id, was in sorted(recorded.items()):
        if assertion_id not in counts:
            # Present but unevaluable is a different report from absent. A run
            # whose subject crashed measures nothing, and calling that a
            # missing assertion — or worse, a pass rate of zero — blames the
            # agent for an infrastructure fault.
            if assertion_id in gaps:
                regressions.append(
                    Regression(
                        "assertion_unmeasured",
                        assertion_id,
                        f"{assertion_id} could not be evaluated in "
                        f"{gaps[assertion_id]} of {len(evidences)} run(s), so "
                        f"there is no rate to compare against the baseline's "
                        f"{was:.0%}",
                    )
                )
                continue
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
