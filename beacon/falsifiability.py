from __future__ import annotations

import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

from beacon.adapters import JSONLCommandAdapter
from beacon.models import AssertionSpec, Evidence, Scenario
from beacon.runner import run_scenario


"""
Whether each assertion in a scenario can actually fail.

The README calls this load-bearing: "An assertion nobody has watched fail is a
claim the evidence does not support." Beacon has enforced it on its own
scenarios since the first release, in `tests/test_falsifiability.py`, and shipped
nothing that let anyone else ask the same question of their own. `validate`
checks structure; it has no opinion about whether an assertion is decorative.

That gap is not cosmetic. `report.md` prints an assertion's description as a
finding whether or not anything could ever have contradicted it, so an
unfalsifiable assertion reads exactly like a passed safety check. "Original
messages were preserved" is a result when a tool could have altered them and a
decoration when none could.

This module is the logic, with no opinion about where the subjects came from.
`cli.py` finds them by convention beside the scenario; Beacon's own suite passes
its four-hundred-entry manifest. Both reach the same answer through the same
code, which is the point: the guard and the shipped feature cannot drift.
"""


def proof_from(evidence: Evidence) -> set[str]:
    """
    The assertions this run proved can fail — by failing them, on purpose.

    `measured` is the whole of it. An assertion that came back
    `passed=False measured=False` was not evaluated: Beacon could not read the
    value, so the run says nothing about whether a subject can make the
    assertion go red. Counting it as proof means a subject that crashes
    "establishes" the falsifiability of every assertion in the scenario, which
    inverts the check — the worst-behaved possible subject would certify the
    most.

    That is not hypothetical. This function replaces one in the test suite that
    collected `not item["passed"]` with no `measured` check, and
    `examples/subjects/crashes_midrun.py` was supplying false proof for four
    assertions under it. The distinction 0.2.0 threaded through the determinism
    signature, the baseline denominator and the repeat set is the same one, in
    the guard whose entire job is to establish that somebody watched a failure.
    """
    return {
        item["id"]
        for item in evidence.assertions
        if item.get("measured", True) and not item["passed"]
    }


#: Types whose threshold can be set so low that no value can violate it.
#:
#: `count_gte path 0` is satisfied by every list including the empty one, so the
#: assertion has no failing case at all — it can only ever be *unmeasured*, by
#: the path being absent. One shipped scenario carried exactly that, and the
#: loose definition of proof above is what kept it invisible: the assertion was
#: "proven" by subjects that omitted the field.
_GTE_TYPES = ("count_gte", "length_gte", "event_count_gte")


def unfalsifiable_by_construction(spec: AssertionSpec) -> str | None:
    """
    Why no subject could break this assertion, or None if one could.

    Static, and worth doing before spending a subprocess per subject: an
    assertion no value can violate is a different finding from one no subject
    happened to violate, and it needs a different fix. Running more subjects
    will never resolve it.
    """
    if spec.type in _GTE_TYPES:
        try:
            threshold = float(spec.expected)
        except (TypeError, ValueError):
            return None
        if threshold <= 0:
            return (
                f"{spec.type} with expected {spec.expected} is satisfied by "
                f"every value, including an empty one, so no subject can make "
                f"it fail"
            )
    return None


@dataclass(frozen=True)
class Subject:
    """One command to run against the scenario, and what to call it."""

    label: str
    command: Sequence[str]
    timeout_seconds: float | None = None

    @classmethod
    def from_script(cls, path: Path, timeout_seconds: float | None = None) -> "Subject":
        return cls(
            label=path.name,
            command=[sys.executable, str(path)],
            timeout_seconds=timeout_seconds,
        )


@dataclass(frozen=True)
class ProofReport:
    """What each assertion's falsifiability rests on, after running the set."""

    scenario_id: str
    #: assertion id -> the subjects that broke it, in the order they were run.
    by_assertion: dict[str, list[str]] = field(default_factory=dict)
    #: assertion id -> why the scenario says no subject can break it.
    exempt: dict[str, str] = field(default_factory=dict)
    #: assertion id -> why no subject *could*, established without running one.
    impossible: dict[str, str] = field(default_factory=dict)
    #: assertion ids that some subject reached but only ever left unmeasured.
    unmeasured_only: tuple[str, ...] = ()
    subjects_run: int = 0

    @property
    def unproven(self) -> tuple[str, ...]:
        """Assertions nothing broke, excluding the ones declared exempt."""
        return tuple(
            assertion
            for assertion, broke in sorted(self.by_assertion.items())
            if not broke and assertion not in self.exempt
        )

    @property
    def ok(self) -> bool:
        return not self.unproven

    def summary(self) -> str:
        lines = [
            f"Falsifiability: {self.scenario_id} against {self.subjects_run} subject(s)."
        ]
        width = max((len(a) for a in self.by_assertion), default=0)
        for assertion, broke in sorted(self.by_assertion.items()):
            if assertion in self.exempt:
                note = f"exempt — {self.exempt[assertion]}"
            elif assertion in self.impossible:
                note = f"UNFALSIFIABLE — {self.impossible[assertion]}"
            elif broke:
                note = f"broken by {', '.join(broke)}"
            elif assertion in self.unmeasured_only:
                # Worth separating. "Nothing broke it" invites writing another
                # subject; "only a crashed subject broke it" means one exists
                # and is not proving what its author thinks it proves.
                note = "UNPROVEN — only ever left unmeasured, never failed"
            else:
                note = "UNPROVEN — no subject makes it fail"
            lines.append(f"  {assertion.ljust(width)}  {note}")
        if self.unproven:
            lines.append(
                f"  {len(self.unproven)} assertion(s) stated in report.md that "
                f"nothing has tested."
            )
        return "\n".join(lines)


def prove(
    scenario: Scenario,
    subjects: Iterable[Subject],
    *,
    output_dir: str | Path | None = None,
    workers: int | None = None,
) -> ProofReport:
    """
    Run every subject against the scenario and report what each assertion rests on.

    Subjects run concurrently, and the reasoning is the one `tests/_subject_runs`
    established: the work is almost entirely waiting on subprocesses, and nothing
    in `beacon/` mutates global state during a run — no `os.chdir`, the service
    registry is written once at import, and every run builds its own recorder,
    services and output directory. Threads rather than processes because the
    payload already *is* process spawning.

    A subject with its own timeout runs first and alone. One that exists to
    exhaust a time budget is measuring elapsed time, and a saturated thread pool
    is precisely what makes elapsed time unpredictable.
    """
    ordered = list(subjects)
    declared = {spec.id: spec for spec in scenario.assertions}

    exempt = {
        spec.id: spec.falsifiable_reason or ""
        for spec in scenario.assertions
        if not spec.falsifiable
    }
    impossible = {}
    for spec in scenario.assertions:
        if spec.id in exempt:
            continue
        why = unfalsifiable_by_construction(spec)
        if why:
            impossible[spec.id] = why

    by_assertion: dict[str, list[str]] = {name: [] for name in declared}
    reached_unmeasured: set[str] = set()

    with tempfile.TemporaryDirectory(prefix="beacon-prove-") as scratch:
        target = Path(output_dir) if output_dir else Path(scratch)

        def _one(index_and_subject: tuple[int, Subject]) -> tuple[str, Evidence]:
            index, subject = index_and_subject
            outcome = run_scenario(
                scenario,
                JSONLCommandAdapter(
                    list(subject.command), timeout_seconds=subject.timeout_seconds
                ),
                output_dir=target,
                # Unique per subject: the runner refuses to write into a
                # directory that already exists, which is right — overwriting a
                # bundle is how evidence stops being evidence.
                run_id=f"prove-{index:04d}-{_slug(subject.label)}",
            )
            return subject.label, outcome.evidence

        timed = [(i, s) for i, s in enumerate(ordered) if s.timeout_seconds is not None]
        rest = [(i, s) for i, s in enumerate(ordered) if s.timeout_seconds is None]

        results: list[tuple[str, Evidence]] = [_one(item) for item in timed]
        if rest:
            pool_size = workers or int(
                os.environ.get("BEACON_PROVE_WORKERS") or min(8, os.cpu_count() or 2)
            )
            if pool_size <= 1:
                results.extend(_one(item) for item in rest)
            else:
                with ThreadPoolExecutor(max_workers=pool_size) as pool:
                    results.extend(pool.map(_one, rest))

    for label, evidence in results:
        broke = proof_from(evidence)
        for name in broke:
            if name in by_assertion:
                by_assertion[name].append(label)
        for item in evidence.assertions:
            if not item.get("measured", True) and not item["passed"]:
                reached_unmeasured.add(item["id"])

    return ProofReport(
        scenario_id=scenario.id,
        by_assertion=by_assertion,
        exempt=exempt,
        impossible=impossible,
        unmeasured_only=tuple(
            sorted(
                name
                for name in reached_unmeasured
                if name in by_assertion and not by_assertion[name]
            )
        ),
        subjects_run=len(ordered),
    )


def _slug(value: str) -> str:
    """A run id component that is safe as a directory name."""
    kept = [c if c.isalnum() or c in "-_" else "-" for c in value]
    return "".join(kept).strip("-")[:48] or "subject"


def discover_subjects(
    scenario_path: Path, timeout_seconds: float | None = None
) -> list[Subject]:
    """
    The subjects that live beside a scenario, which is what `init` scaffolds.

    `subjects/*.py`, sorted, skipping `_`-prefixed files so a shared helper is
    not run as a subject in its own right. Convention rather than configuration
    because the scaffold already writes `compliant.py` and `violating.py` there
    and tells the author to keep editing the second one — this is the command
    that finally reads them.
    """
    directory = scenario_path.parent / "subjects"
    if not directory.is_dir():
        return []
    return [
        Subject.from_script(path, timeout_seconds)
        for path in sorted(directory.glob("*.py"))
        if not path.name.startswith("_")
    ]
