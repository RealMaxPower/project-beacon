from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from beacon.baseline import (
    build_baseline,
    compare_to_baseline,
    load_baseline,
    load_recent_evidence,
    save_baseline,
    subject_identity,
    wilson_interval,
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

    def test_one_unlucky_run_of_a_flaky_subject_is_not_a_regression(self) -> None:
        """
        The case that would have made this useless in CI. An agent that truly
        passes a third of the time fails a single run two times in three; if
        each of those is reported as a regression the check gets deleted.
        """
        baseline = build_baseline(_runs([True, False, False] * 4))
        one_bad_run = [_evidence("r", {"stable-one": True, "flaky-one": False}, "FAIL")]
        self.assertFalse(compare_to_baseline(one_bad_run, baseline).regressed)

    def test_one_run_still_catches_a_reliable_subject_breaking(self) -> None:
        """
        Noise tolerance must not become blindness: the same single failing run
        that means nothing against a flaky baseline is conclusive against a
        baseline that never failed.
        """
        baseline = build_baseline(_runs([True] * 20))
        one_bad_run = [_evidence("r", {"stable-one": True, "flaky-one": False}, "FAIL")]
        comparison = compare_to_baseline(one_bad_run, baseline)
        self.assertTrue(comparison.regressed)
        self.assertEqual(comparison.regressions[0].assertion_id, "flaky-one")

    def test_the_detail_line_shows_the_counts_behind_the_rate(self) -> None:
        """A percentage from one run and from fifty read identically otherwise."""
        baseline = build_baseline(_runs([True] * 20))
        comparison = compare_to_baseline(_runs([False] * 4), baseline)
        self.assertIn("(0/4)", comparison.regressions[0].detail)

    def test_a_small_improvement_is_not_claimed_from_one_run(self) -> None:
        baseline = build_baseline(_runs([True, False] * 6))
        self.assertEqual(
            compare_to_baseline(_runs([True]), baseline).improvements, ()
        )

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


class WilsonIntervalTests(unittest.TestCase):
    def test_it_stays_sensible_where_the_normal_approximation_collapses(self) -> None:
        """
        At n=1 with no successes the textbook interval is [0, 0] — certainty
        from a single observation. That failure mode is the reason for Wilson.
        """
        low, high = wilson_interval(0, 1)
        self.assertEqual(low, 0.0)
        self.assertGreater(high, 0.7)

    def test_a_larger_sample_narrows_the_interval(self) -> None:
        _, small = wilson_interval(0, 2)
        _, large = wilson_interval(0, 40)
        self.assertLess(large, small)

    def test_it_never_leaves_the_unit_interval(self) -> None:
        for passed, total in ((0, 1), (1, 1), (5, 5), (0, 100), (50, 100)):
            low, high = wilson_interval(passed, total)
            self.assertGreaterEqual(low, 0.0)
            self.assertLessEqual(high, 1.0)

    def test_no_observations_means_no_information(self) -> None:
        self.assertEqual(wilson_interval(0, 0), (0.0, 1.0))


class SubjectIdentityTests(unittest.TestCase):
    def test_two_hosted_agents_are_not_the_same_subject(self) -> None:
        """
        Every A2A subject reports id "a2a". Comparing one hosted agent's pass
        rate against another's and calling the difference a regression is the
        specific mistake this key exists to prevent.
        """
        self.assertNotEqual(
            subject_identity({"id": "a2a", "adapter": "a2a", "agent_url": "https://a"}),
            subject_identity({"id": "a2a", "adapter": "a2a", "agent_url": "https://b"}),
        )

    def test_two_command_subjects_are_told_apart_by_their_command(self) -> None:
        """Every command subject reports id 'jsonl-command'; only the command differs."""
        base = {"id": "jsonl-command", "adapter": "jsonl-command"}
        self.assertNotEqual(
            subject_identity({**base, "command": ["python3", "good.py"]}),
            subject_identity({**base, "command": ["python3", "bad.py"]}),
        )

    def test_a_renamed_agent_is_still_the_same_subject(self) -> None:
        self.assertEqual(
            subject_identity({"id": "a2a", "agent_url": "https://a", "name": "Old"}),
            subject_identity({"id": "a2a", "agent_url": "https://a", "name": "New"}),
        )

    def test_a_baseline_matches_the_runs_it_was_built_from(self) -> None:
        """
        Caught live: the baseline stored only some descriptor fields, so a
        command subject's baseline reported a different subject than the run
        that produced it, on every single comparison.
        """
        runs = _runs([True, True])
        for evidence in runs:
            evidence.subject = {
                "id": "jsonl-command",
                "adapter": "jsonl-command",
                "name": "agent",
                "command": ["python3", "agent.py"],
            }
        comparison = compare_to_baseline(runs, build_baseline(runs))
        self.assertFalse(comparison.subject_changed)

    def test_comparing_against_another_subjects_baseline_is_flagged(self) -> None:
        baseline = build_baseline(_runs([True, True]))
        baseline["subject"] = {"id": "a2a", "adapter": "a2a", "agent_url": "https://b"}
        comparison = compare_to_baseline(_runs([True, True]), baseline)
        self.assertTrue(comparison.subject_changed)
        self.assertIn("different subject", comparison.summary())


class RecentEvidenceTests(unittest.TestCase):
    """
    The rolling baseline reads history out of the output directory rather than
    a committed file. A shared output directory is the normal case, so the
    filtering is the whole feature.
    """

    def _write(self, root: Path, evidence: Evidence) -> None:
        directory = root / evidence.run_id
        directory.mkdir(parents=True)
        (directory / "evidence.json").write_text(
            json.dumps(evidence.to_dict()), encoding="utf-8"
        )

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_runs_come_back_oldest_first(self) -> None:
        for index in range(4):
            evidence = _evidence(f"run-{index}", {"a": True}, "PASS")
            evidence.started_at = f"2026-07-0{index + 1}T00:00:00+00:00"
            self._write(self.root, evidence)
        found = load_recent_evidence(self.root)
        self.assertEqual([item.run_id for item in found], ["run-0", "run-1", "run-2", "run-3"])

    def test_only_the_last_n_are_returned(self) -> None:
        for index in range(6):
            evidence = _evidence(f"run-{index}", {"a": True}, "PASS")
            evidence.started_at = f"2026-07-0{index + 1}T00:00:00+00:00"
            self._write(self.root, evidence)
        found = load_recent_evidence(self.root, limit=2)
        self.assertEqual([item.run_id for item in found], ["run-4", "run-5"])

    def test_this_runs_own_bundles_are_excluded(self) -> None:
        for index in range(3):
            self._write(self.root, _evidence(f"run-{index}", {"a": True}, "PASS"))
        found = load_recent_evidence(self.root, exclude_run_ids=["run-1", "run-2"])
        self.assertEqual([item.run_id for item in found], ["run-0"])

    def test_another_scenario_in_the_same_directory_is_skipped(self) -> None:
        mine = _evidence("mine", {"a": True}, "PASS")
        theirs = _evidence("theirs", {"a": True}, "PASS")
        theirs.scenario = {"id": "something-else"}
        self._write(self.root, mine)
        self._write(self.root, theirs)
        found = load_recent_evidence(self.root, like=mine, exclude_run_ids=["mine"])
        self.assertEqual(found, [])

    def test_another_agent_in_the_same_directory_is_skipped(self) -> None:
        mine = _evidence("mine", {"a": True}, "PASS")
        mine.subject = {"id": "a2a", "adapter": "a2a", "agent_url": "https://mine"}
        theirs = _evidence("theirs", {"a": True}, "PASS")
        theirs.subject = {"id": "a2a", "adapter": "a2a", "agent_url": "https://theirs"}
        self._write(self.root, mine)
        self._write(self.root, theirs)
        found = load_recent_evidence(self.root, like=mine, exclude_run_ids=["mine"])
        self.assertEqual(found, [])

    def test_a_corrupt_bundle_does_not_break_the_run(self) -> None:
        """
        History is a convenience. A half-written bundle should cost you the
        comparison, not the run you are in the middle of.
        """
        self._write(self.root, _evidence("good", {"a": True}, "PASS"))
        broken = self.root / "broken"
        broken.mkdir()
        (broken / "evidence.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(
            [item.run_id for item in load_recent_evidence(self.root)], ["good"]
        )

    def test_an_empty_directory_yields_no_history(self) -> None:
        self.assertEqual(load_recent_evidence(self.root), [])

    def test_a_missing_directory_yields_no_history(self) -> None:
        self.assertEqual(load_recent_evidence(self.root / "nope"), [])


class EvidenceRoundTripTests(unittest.TestCase):
    def test_a_bundle_survives_a_trip_through_disk(self) -> None:
        original = _evidence("run-1", {"a": True, "b": False}, "FAIL")
        restored = Evidence.from_dict(original.to_dict())
        self.assertEqual(restored.to_dict(), original.to_dict())

    def test_the_digest_is_preserved_rather_than_recomputed(self) -> None:
        """Re-grading offline must not silently re-sign someone else's bundle."""
        original = _evidence("run-1", {"a": True}, "PASS")
        self.assertEqual(Evidence.from_dict(original.to_dict()).digest, original.digest)

    def test_an_unrecognised_field_is_refused(self) -> None:
        payload = _evidence("run-1", {"a": True}, "PASS").to_dict()
        payload["invented_field"] = 1
        with self.assertRaises(ValueError):
            Evidence.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
