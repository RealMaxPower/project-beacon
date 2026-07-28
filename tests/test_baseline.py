from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from beacon.baseline import (
    build_baseline,
    compare_to_baseline,
    load_baseline,
    save_baseline,
)
from beacon.determinism import compare_runs
from beacon.models import Evidence


def _evidence(run_id: str, assertions: dict[str, bool], result: str) -> Evidence:
    evidence = Evidence(
        evidence_version="0.1",
        run_id=run_id,
        started_at="2026-07-01T00:00:00+00:00",
        completed_at="2026-07-01T00:00:01+00:00",
        scenario={"id": "probe"},
        subject={"id": "a2a", "name": "agent", "adapter": "a2a"},
        result=result,
        assertions=[
            {"id": key, "passed": value} for key, value in assertions.items()
        ],
        state={"before_digest": "b", "after_digest": "a"},
        state_diff={"change_count": 0, "changes": []},
        events=[],
        artifacts={"answer": "x"},
        usage={"calls": 1},
        reset_verified=True,
        limitations=[],
    )
    evidence.finalize()
    return evidence


def _runs(pattern: list[bool]) -> list[Evidence]:
    """One run per entry; True means the flaky assertion passed."""
    return [
        _evidence(
            f"run-{index:03d}",
            {"stable-one": True, "flaky-one": ok},
            "PASS" if ok else "FAIL",
        )
        for index, ok in enumerate(pattern, start=1)
    ]


class FlakinessReportTests(unittest.TestCase):
    """
    A binary STABLE/DIVERGENT says something moved. It does not say how often,
    and an intermittent failure looks like a pass most of the time — which is
    how the extractor read as fine on four runs out of five.
    """

    def test_a_flaky_assertion_is_named_with_its_rate(self) -> None:
        report = compare_runs(_runs([True, False, False, True, False, False]))
        self.assertFalse(report.stable)
        self.assertEqual(len(report.flaky), 1)
        flaky = report.flaky[0]
        self.assertEqual(flaky.id, "flaky-one")
        self.assertEqual((flaky.passed, flaky.total), (2, 6))
        self.assertAlmostEqual(flaky.pass_rate, 1 / 3)

    def test_the_runs_that_failed_are_identified(self) -> None:
        report = compare_runs(_runs([True, False, True, False]))
        self.assertEqual(
            report.flaky[0].failed_runs, ("run-002", "run-004")
        )

    def test_an_assertion_that_always_passes_is_not_flaky(self) -> None:
        report = compare_runs(_runs([True, True, True]))
        self.assertEqual(report.flaky, ())
        self.assertTrue(report.stable)

    def test_an_assertion_that_always_fails_is_not_flaky_either(self) -> None:
        """Consistently broken is a different problem from intermittently broken."""
        report = compare_runs(_runs([False, False, False]))
        self.assertEqual(report.flaky, ())
        self.assertTrue(report.stable)

    def test_the_verdict_split_is_reported_as_a_rate(self) -> None:
        report = compare_runs(_runs([True, False, False, False]))
        self.assertEqual(report.verdicts, {"PASS": 1, "FAIL": 3})
        self.assertEqual(report.dominant_verdict, "FAIL")
        summary = report.summary()
        self.assertIn("FAIL 3 (75%)", summary)
        self.assertIn("flaky-one passed 1/4 (25%)", summary)


class BaselineTests(unittest.TestCase):
    def test_a_baseline_records_pass_rates_not_just_verdicts(self) -> None:
        baseline = build_baseline(_runs([True, False, True, True]))
        self.assertEqual(baseline["assertion_pass_rates"]["stable-one"], 1.0)
        self.assertEqual(baseline["assertion_pass_rates"]["flaky-one"], 0.75)
        self.assertEqual(baseline["runs"], 4)

    def test_an_unchanged_subject_reports_no_change(self) -> None:
        runs = _runs([True, False, True, True])
        comparison = compare_to_baseline(runs, build_baseline(runs))
        self.assertFalse(comparison.regressed)
        self.assertIn("No change", comparison.summary())

    def test_a_dropped_pass_rate_is_a_regression(self) -> None:
        baseline = build_baseline(_runs([True, True, True, True]))
        comparison = compare_to_baseline(_runs([True, False, False, False]), baseline)
        self.assertTrue(comparison.regressed)
        self.assertEqual(comparison.regressions[0].assertion_id, "flaky-one")
        self.assertIn("100%", comparison.regressions[0].detail)
        self.assertIn("25%", comparison.regressions[0].detail)

    def test_an_intermittent_regression_is_visible_that_one_run_would_miss(self) -> None:
        """
        The case that motivates comparing rates rather than verdicts: a subject
        failing a quarter of the time still passes three comparisons in four.
        """
        baseline = build_baseline(_runs([True] * 8))
        degraded = _runs([True, True, True, False] * 2)
        self.assertTrue(compare_to_baseline(degraded, baseline).regressed)
        # A single lucky run agrees with the baseline and hides it.
        self.assertFalse(compare_to_baseline(_runs([True]), baseline).regressed)

    def test_an_improvement_is_reported_but_is_not_a_regression(self) -> None:
        baseline = build_baseline(_runs([True, False, False, False]))
        comparison = compare_to_baseline(_runs([True] * 4), baseline)
        self.assertFalse(comparison.regressed)
        self.assertTrue(comparison.improvements)

    def test_tolerance_absorbs_sampling_noise(self) -> None:
        baseline = build_baseline(_runs([True] * 10))
        slightly_worse = _runs([True] * 9 + [False])
        self.assertTrue(compare_to_baseline(slightly_worse, baseline).regressed)
        self.assertFalse(
            compare_to_baseline(slightly_worse, baseline, tolerance=0.2).regressed
        )

    def test_an_assertion_missing_since_the_baseline_is_a_regression(self) -> None:
        baseline = build_baseline(_runs([True, True]))
        thinner = [_evidence("run-001", {"stable-one": True}, "PASS")]
        comparison = compare_to_baseline(thinner, baseline)
        self.assertTrue(comparison.regressed)
        self.assertEqual(comparison.regressions[0].kind, "assertion_missing")

    def test_a_new_assertion_is_an_improvement_not_a_regression(self) -> None:
        baseline = build_baseline([_evidence("r", {"stable-one": True}, "PASS")])
        comparison = compare_to_baseline(_runs([True, True]), baseline)
        self.assertFalse(comparison.regressed)
        self.assertEqual(comparison.improvements[0].kind, "assertion_added")

    def test_a_baseline_round_trips_through_disk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "baseline.json"
            save_baseline(_runs([True, False]), path)
            self.assertEqual(load_baseline(path)["runs"], 2)

    def test_an_unknown_baseline_version_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            path.write_text(json.dumps({"baseline_version": "9.9"}))
            with self.assertRaises(ValueError):
                load_baseline(path)

    def test_a_baseline_cannot_be_built_from_nothing(self) -> None:
        with self.assertRaises(ValueError):
            build_baseline([])


if __name__ == "__main__":
    unittest.main()
