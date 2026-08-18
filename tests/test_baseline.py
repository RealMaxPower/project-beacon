from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from beacon.baseline import (
    _counts,
    build_baseline,
    compare_to_baseline,
    load_baseline,
    load_recent_evidence,
    portable_command,
    save_baseline,
    subject_identity,
    wilson_interval,
)
from beacon.determinism import compare_runs
from beacon.models import REQUIRED_EVIDENCE_FIELDS, Evidence


def _evidence(run_id: str, assertions: dict[str, bool], result: str) -> Evidence:
    evidence = Evidence(
        evidence_version="0.2",
        run_id=run_id,
        started_at="2026-07-01T00:00:00+00:00",
        completed_at="2026-07-01T00:00:01+00:00",
        scenario={"id": "probe"},
        subject={"id": "a2a", "name": "agent", "adapter": "a2a"},
        result=result,
        assertions=[
            {"id": key, "passed": value} for key, value in assertions.items()
        ],
        # `before` and `after` carry the snapshots themselves, which every
        # bundle Beacon writes contains and which `run_signature` compares by
        # shape. The digests beside them stay exact.
        state={
            "before_digest": "b",
            "after_digest": "a",
            "before": {"mail": {"drafts": []}},
            "after": {"mail": {"drafts": []}},
        },
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

    def test_a_bundle_missing_its_verdict_does_not_break_the_run(self) -> None:
        """
        The bundle above is broken in a way `json` catches. This one is not:
        it parses, and then `from_dict` walks off the end of it.

        That used to raise KeyError, which this loader does not catch and the
        CLI does not either, so a truncated bundle in a shared output directory
        turned `--baseline-recent` into a traceback — for a run that had already
        finished and been graded.
        """
        self._write(self.root, _evidence("good", {"a": True}, "PASS"))
        for name, payload in (
            ("no-verdict", {"run_id": "no-verdict"}),
            ("no-id", {"result": "PASS"}),
            ("empty", {}),
        ):
            directory = self.root / name
            directory.mkdir()
            (directory / "evidence.json").write_text(
                json.dumps(payload), encoding="utf-8"
            )
        self.assertEqual(
            [item.run_id for item in load_recent_evidence(self.root)], ["good"]
        )

    def test_a_bundle_that_is_not_an_object_does_not_break_the_run(self) -> None:
        """Valid JSON, wrong shape. This one used to escape as TypeError."""
        self._write(self.root, _evidence("good", {"a": True}, "PASS"))
        for name, text in (("array", "[1, 2]"), ("scalar", "5"), ("null", "null")):
            directory = self.root / name
            directory.mkdir()
            (directory / "evidence.json").write_text(text, encoding="utf-8")
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

    def test_a_bundle_missing_a_required_field_is_refused(self) -> None:
        """
        ValueError, not KeyError, and the message has to name the field.

        `project-beacon run` prints the exception and nothing else, so a bare
        KeyError reached the operator as `error: 'run_id'` — which does not
        say what was being read or what was wrong with it.
        """
        for name in REQUIRED_EVIDENCE_FIELDS:
            with self.subTest(field=name):
                payload = _evidence("run-1", {"a": True}, "PASS").to_dict()
                del payload[name]
                with self.assertRaises(ValueError) as caught:
                    Evidence.from_dict(payload)
                self.assertIn(name, str(caught.exception))

    def test_a_bundle_that_is_not_an_object_is_refused(self) -> None:
        for value in ([], None, 5, "text"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    Evidence.from_dict(value)  # type: ignore[arg-type]

    def test_every_other_field_still_defaults(self) -> None:
        """
        The guard is two fields wide on purpose. Widening it would break the
        thing `from_dict` exists to do — read a bundle written by an older
        version — so this pins the boundary rather than the exception.
        """
        restored = Evidence.from_dict({"run_id": "run-1", "result": "PASS"})
        self.assertEqual(restored.run_id, "run-1")
        self.assertEqual(restored.result, "PASS")
        self.assertEqual(restored.assertions, [])
        self.assertEqual(restored.limitations, [])
        self.assertFalse(restored.reset_verified)


class UnmeasuredIsNotAFailureTests(unittest.TestCase):
    """
    A run that could not be evaluated is a gap, not the agent getting worse.

    Found by a reviewer whose model server was OOM-killed mid-run. The subject
    errored, the run reported INCOMPLETE with `task-completed passed=False
    measured=False`, and the baseline comparison announced:

        REGRESSION  task-completed passed 100% of baseline runs, 0% now (0/1)

    `_counts` read `passed` and ignored `measured`, so an assertion nothing
    could evaluate entered the denominator as a failure. `cli.py` then exits
    non-zero, which fails CI and blames the agent for an infrastructure fault —
    the most expensive kind of wrong answer this tool can give, because the
    natural response is to go looking for a regression that is not there.
    """

    @staticmethod
    def _crashed(run_id: str) -> Evidence:
        evidence = _evidence(run_id, {"task-completed": False}, "INCOMPLETE")
        for item in evidence.assertions:
            item["measured"] = False
        return evidence

    def test_an_unmeasured_assertion_leaves_the_denominator(self) -> None:
        counts = _counts([self._crashed("crash-1")])
        self.assertEqual(
            counts.get("task-completed"),
            None,
            "an assertion nothing could evaluate was counted as a failed run",
        )

    def test_a_crashed_run_reports_a_gap_rather_than_a_regression(self) -> None:
        baseline = build_baseline([_evidence("base", {"task-completed": True}, "PASS")])
        self.assertEqual(baseline["assertion_pass_rates"]["task-completed"], 1.0)

        comparison = compare_to_baseline([self._crashed("crash-1")], baseline)
        kinds = [regression.kind for regression in comparison.regressions]
        self.assertIn(
            "assertion_unmeasured",
            kinds,
            "a run that measured nothing did not report the gap",
        )
        self.assertNotIn(
            "pass_rate_dropped",
            kinds,
            "an infrastructure fault was reported as the agent regressing",
        )

    def test_a_real_regression_is_still_reported(self) -> None:
        """The control. A fix for this must not silence the thing it exists for."""
        baseline = build_baseline(
            [_evidence(f"base-{i}", {"task-completed": True}, "PASS") for i in range(5)]
        )
        measured_failures = [
            _evidence(f"now-{i}", {"task-completed": False}, "FAIL") for i in range(5)
        ]
        comparison = compare_to_baseline(measured_failures, baseline)
        self.assertIn(
            "pass_rate_dropped", [r.kind for r in comparison.regressions]
        )


class PortableIdentityTests(unittest.TestCase):
    """
    A baseline is a file people commit, so it must not name their machine.

    `subject_identity` hashed the whole argv, which the adapter resolves to
    absolute paths. Five baselines recorded for a model ladder carried
    `/tmp/pv/bin/python` and `/tmp/sd/project_beacon-0.1.2/examples/agent.py`,
    so comparing against them from any other directory produced "this baseline
    was recorded against a different subject. The comparison below is not
    meaningful" — which is every use `baselines/` exists for.

    The committed `inbox-briefing.reference.json` escaped only because the
    in-process adapter records `command: null`, so nothing here had ever
    exercised the case the directory is named for.
    """

    LADDER = ["/tmp/pv/bin/python", "/tmp/sd/project_beacon-0.1.2/examples/agent.py",
              "--base-url", "http://localhost:11434/v1", "--model", "qwen2.5:3b"]
    ELSEWHERE = ["/opt/venv/bin/python", "/srv/checkout/examples/agent.py",
                 "--base-url", "http://localhost:11434/v1", "--model", "qwen2.5:3b"]

    def _identity(self, command):
        return subject_identity(
            {"id": "jsonl-command", "adapter": "jsonl-command",
             "agent_url": None, "server_url": None, "command": command}
        )

    def test_the_same_subject_compares_equal_from_another_checkout(self) -> None:
        self.assertEqual(self._identity(self.LADDER), self._identity(self.ELSEWHERE))

    def test_a_different_model_is_still_a_different_subject(self) -> None:
        """
        The scrub must not go so far that the ladder collapses.

        These five baselines share a name, an id and an adapter, and differ only
        in `--model`. Scrubbing the whole command would make them one subject
        with five contradictory histories, which is worse than the bug.
        """
        other = list(self.ELSEWHERE)
        other[-1] = "qwen2.5:7b"
        self.assertNotEqual(self._identity(self.ELSEWHERE), self._identity(other))

    def test_no_absolute_path_is_written_into_a_saved_baseline(self) -> None:
        evidence = _evidence("run", {"a": True}, "PASS")
        evidence.subject = {**evidence.subject, "command": self.LADDER}
        stored = build_baseline([evidence])["subject"]["command"]
        for token in stored:
            with self.subTest(token=token):
                self.assertFalse(
                    token.startswith("/"),
                    f"a saved baseline names the recording machine: {token}",
                )
        # What distinguishes the subject has to survive the scrub.
        self.assertIn("--model", stored)
        self.assertIn("qwen2.5:3b", stored)
        self.assertTrue(any(t.endswith("agent.py") for t in stored))

    def test_a_null_command_is_untouched(self) -> None:
        """The in-process adapter records none, and that is not a path."""
        self.assertIsNone(portable_command(None))

    def test_no_committed_baseline_names_a_machine(self) -> None:
        """
        The rule applied to the files actually in the repository.

        The tests above check the function; this checks the artefacts, which is
        the thing a reader clones. A baseline recorded before the scrub existed,
        or written by hand, would carry a home directory into a public
        repository — and the model ladder that prompted this arrived carrying
        `/tmp/pv/bin/python` and a `/tmp/sd/...` checkout path.
        """
        directory = Path(__file__).resolve().parents[1] / "baselines"
        committed = sorted(directory.glob("*.json"))
        self.assertGreater(len(committed), 0, "no committed baselines to check")

        offenders = []
        for path in committed:
            command = json.loads(path.read_text(encoding="utf-8"))["subject"].get("command")
            for token in command or []:
                if token.startswith("/") or (len(token) > 3 and token[1] == ":"):
                    offenders.append(f"{path.name}: {token}")
        self.assertEqual(offenders, [], f"committed baselines name a machine: {offenders}")


if __name__ == "__main__":
    unittest.main()
