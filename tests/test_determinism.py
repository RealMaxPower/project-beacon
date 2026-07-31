from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from beacon.adapters import ReferenceInboxAdapter
from beacon.cli import main
from beacon.determinism import (
    compare_runs,
    repeat_run_ids,
    run_signature,
    tool_sequence,
)
from beacon.models import Evidence, Scenario
from beacon.runner import run_scenario


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios" / "inbox-briefing" / "scenario.json"


def _evidence(
    *,
    run_id: str = "run-a",
    started_at: str = "2026-01-01T00:00:00+00:00",
    result: str = "PASS",
    after_digest: str = "digest-after",
    after: dict[str, Any] | None = None,
    assertions: list[dict[str, Any]] | None = None,
    artifacts: dict[str, Any] | None = None,
    tool_targets: tuple[str, ...] = ("mail_list_messages",),
) -> Evidence:
    evidence = Evidence(
        evidence_version="0.1",
        run_id=run_id,
        started_at=started_at,
        completed_at=started_at,
        scenario={"id": "s"},
        subject={"id": "subject"},
        result=result,
        assertions=assertions
        if assertions is not None
        else [{"id": "one", "passed": True}],
        state={
            "before_digest": "digest-before",
            "after_digest": after_digest,
            "before": {"mail": {"drafts": []}},
            "after": after if after is not None else {"mail": {"drafts": []}},
        },
        state_diff={"change_count": 0, "changes": []},
        events=[
            {"sequence": index, "kind": "tool_call", "target": target}
            for index, target in enumerate(tool_targets, start=1)
        ],
        artifacts=artifacts if artifacts is not None else {"summary": "text"},
        usage={"calls": 0, "total_seconds": 0.0},
        reset_verified=True,
        limitations=[],
    )
    evidence.finalize()
    return evidence


class SignatureTests(unittest.TestCase):
    def test_volatile_fields_do_not_affect_the_signature(self) -> None:
        first = _evidence(run_id="run-a", started_at="2026-01-01T00:00:00+00:00")
        second = _evidence(run_id="run-b", started_at="2027-06-30T12:00:00+00:00")
        self.assertNotEqual(first.digest, second.digest)
        self.assertEqual(run_signature(first), run_signature(second))

    def test_artifact_content_is_excluded_but_names_are_not(self) -> None:
        baseline = _evidence(artifacts={"summary": "one wording"})
        reworded = _evidence(artifacts={"summary": "an entirely different wording"})
        renamed = _evidence(artifacts={"briefing": "one wording"})
        self.assertTrue(compare_runs([baseline, reworded]).stable)
        report = compare_runs([baseline, renamed])
        self.assertFalse(report.stable)
        self.assertIn("artifact_names", report.divergent_fields)


class StateShapeTests(unittest.TestCase):
    """
    State is compared by shape, so a subject that rephrases is not called
    non-deterministic — and one that behaves differently still is.

    Five runs of `inbox-briefing` against a real model returned PASS with an
    identical assertion vector and identical draft metadata every time, and
    were reported DIVERGENT anyway, exiting non-zero, because the model chose
    different words inside the drafts. Artifact wording was already excluded
    from the comparison for exactly this reason; state was not, so the CI
    recipe in `docs/agent-builders.md` failed every run for any scenario whose
    subject writes prose into a service.

    The cases below are the ones that must still diverge. Without them this
    change would read as "make the check pass", which is not what it is.
    """

    def _drafts(self, *drafts: dict[str, Any]) -> dict[str, Any]:
        return {"mail": {"drafts": list(drafts), "sent": []}}

    BODY = {"id": "d-1", "in_reply_to": "m-1", "body": "Hi Maya, confirming."}

    def test_rewording_alone_is_not_divergence(self) -> None:
        reworded = dict(self.BODY, body="Hi Maya, I can confirm that.")
        report = compare_runs(
            [
                _evidence(after=self._drafts(self.BODY), after_digest="a"),
                _evidence(after=self._drafts(reworded), after_digest="b"),
            ]
        )
        self.assertTrue(report.stable, report.divergent_fields)

    def test_rewording_is_still_reported_rather_than_passed_over(self) -> None:
        """Tolerated is not the same as unmentioned."""
        reworded = dict(self.BODY, body="Hi Maya, I can confirm that.")
        report = compare_runs(
            [
                _evidence(after=self._drafts(self.BODY), after_digest="a"),
                _evidence(after=self._drafts(reworded), after_digest="b"),
            ]
        )
        self.assertTrue(report.state_text_differs)
        self.assertIn("matched in shape", report.summary())

    def test_identical_text_reports_no_text_difference(self) -> None:
        """Otherwise the note above would be printed for every stable run."""
        report = compare_runs(
            [
                _evidence(after=self._drafts(self.BODY), after_digest="a"),
                _evidence(after=self._drafts(self.BODY), after_digest="a"),
            ]
        )
        self.assertFalse(report.state_text_differs)
        self.assertNotIn("matched in shape", report.summary())

    def test_a_structural_change_still_diverges(self) -> None:
        second = dict(self.BODY, id="d-2")
        cases = {
            "an extra draft": self._drafts(self.BODY, second),
            "a missing draft": self._drafts(),
            "a dropped key": self._drafts({"id": "d-1", "body": "Hi Maya."}),
            "a renamed key": self._drafts(
                {"id": "d-1", "replies_to": "m-1", "body": "Hi Maya."}
            ),
            "a message actually sent": {
                "mail": {"drafts": [self.BODY], "sent": [{"id": "m-1"}]}
            },
            "a body that is empty": self._drafts(dict(self.BODY, body="")),
            "a changed number": {
                "mail": {"drafts": [self.BODY], "sent": [], "unread": 2}
            },
            "a changed flag": {
                "mail": {"drafts": [self.BODY], "sent": [], "locked": True}
            },
        }
        for label, mutated in cases.items():
            with self.subTest(change=label):
                report = compare_runs(
                    [
                        _evidence(after=self._drafts(self.BODY), after_digest="a"),
                        _evidence(after=mutated, after_digest="b"),
                    ]
                )
                self.assertFalse(
                    report.stable, f"{label} was tolerated as a rewording"
                )
                self.assertIn("after_state", report.divergent_fields)

    def test_the_exact_digest_is_still_recorded_in_the_evidence(self) -> None:
        """
        Comparing by shape must not weaken the tamper-evidence digest, which
        answers a different question and is taken over the whole document.
        """
        evidence = _evidence(after=self._drafts(self.BODY), after_digest="exact")
        self.assertEqual(evidence.state["after_digest"], "exact")


class CompareRunsTests(unittest.TestCase):
    def test_identical_runs_are_stable(self) -> None:
        report = compare_runs([_evidence(), _evidence(), _evidence()])
        self.assertTrue(report.stable)
        self.assertEqual(report.run_count, 3)
        self.assertEqual(report.divergent_fields, ())
        self.assertIn("STABLE", report.summary())

    def test_divergent_verdict_and_state_are_both_named(self) -> None:
        report = compare_runs(
            [
                _evidence(result="PASS", after={"mail": {"drafts": [{"id": "d-1"}]}}),
                _evidence(result="FAIL", after={"mail": {"drafts": []}}),
            ]
        )
        self.assertFalse(report.stable)
        self.assertIn("result", report.divergent_fields)
        self.assertIn("after_state", report.divergent_fields)
        self.assertIn("DIVERGENT", report.summary())

    def test_assertion_vector_divergence_is_detected(self) -> None:
        report = compare_runs(
            [
                _evidence(assertions=[{"id": "one", "passed": True}]),
                _evidence(assertions=[{"id": "one", "passed": False}]),
            ]
        )
        self.assertFalse(report.stable)
        self.assertIn("assertions", report.divergent_fields)

    def test_tool_order_is_reported_but_does_not_break_stability(self) -> None:
        report = compare_runs(
            [
                _evidence(tool_targets=("mail_list_messages", "mail_read_message")),
                _evidence(tool_targets=("mail_read_message", "mail_list_messages")),
            ]
        )
        self.assertTrue(report.stable)
        self.assertTrue(report.tool_sequences_differ)
        self.assertIn("tool-call order varied", report.summary())

    def test_empty_comparison_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            compare_runs([])

    def test_tool_sequence_ignores_non_tool_events(self) -> None:
        evidence = _evidence(tool_targets=("mail_list_messages",))
        evidence.events.append(
            {"sequence": 99, "kind": "subject_log", "target": "noise"}
        )
        self.assertEqual(tool_sequence(evidence), ("mail_list_messages",))


class RepeatRunIdTests(unittest.TestCase):
    def test_generated_ids_are_left_to_the_runner(self) -> None:
        self.assertEqual(list(repeat_run_ids(None, 3)), [None, None, None])

    def test_single_run_keeps_the_supplied_id_unsuffixed(self) -> None:
        self.assertEqual(list(repeat_run_ids("nightly", 1)), ["nightly"])

    def test_repeats_are_suffixed(self) -> None:
        self.assertEqual(
            list(repeat_run_ids("nightly", 3)),
            ["nightly-001", "nightly-002", "nightly-003"],
        )


class RepeatedRunTests(unittest.TestCase):
    def test_reference_subject_is_stable_across_repeats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidences = [
                run_scenario(
                    Scenario.load(SCENARIO),
                    ReferenceInboxAdapter(),
                    output_dir=directory,
                    run_id=f"repeat-{index}",
                ).evidence
                for index in range(3)
            ]
        report = compare_runs(evidences)
        self.assertTrue(report.stable, report.summary())
        self.assertFalse(report.tool_sequences_differ)

    def test_cli_repeat_exits_zero_when_stable_and_passing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            code = main(
                [
                    "run",
                    str(SCENARIO),
                    "--output",
                    directory,
                    "--run-id",
                    "cli-repeat",
                    "--repeat",
                    "3",
                ]
            )
        self.assertEqual(code, 0)

    def test_cli_rejects_a_repeat_below_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            code = main(
                ["run", str(SCENARIO), "--output", directory, "--repeat", "0"]
            )
        self.assertEqual(code, 2)


class RollingBaselineCLITests(unittest.TestCase):
    """`--baseline-recent` reads its history out of the output directory."""

    def setUp(self) -> None:
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory, True)

    def _run(self, *extra: str) -> int:
        return main(["run", str(SCENARIO), "--output", self.directory, *extra])

    def test_the_first_run_has_nothing_to_compare_against_and_still_passes(self) -> None:
        self.assertEqual(self._run("--baseline-recent", "5"), 0)

    def test_an_unchanged_subject_reports_no_regression(self) -> None:
        self._run("--run-id", "history", "--repeat", "3")
        self.assertEqual(self._run("--baseline-recent", "5"), 0)

    def test_the_current_runs_do_not_become_their_own_baseline(self) -> None:
        """
        Comparing a run against itself always says "no change", which would
        make the check pass unconditionally.
        """
        self.assertEqual(
            self._run("--run-id", "solo", "--repeat", "3", "--baseline-recent", "5"), 0
        )
        recorded = sorted(path.parent.name for path in Path(self.directory).glob("*/evidence.json"))
        self.assertEqual(recorded, ["solo-001", "solo-002", "solo-003"])

    def test_the_two_baseline_modes_are_mutually_exclusive(self) -> None:
        code = self._run(
            "--baseline", str(Path(self.directory) / "b.json"), "--baseline-recent", "5"
        )
        self.assertEqual(code, 2)

    def test_a_window_below_one_is_refused(self) -> None:
        self.assertEqual(self._run("--baseline-recent", "0"), 2)

    def test_a_tolerance_outside_zero_to_one_is_refused(self) -> None:
        self.assertEqual(self._run("--baseline-recent", "5", "--baseline-tolerance", "1.5"), 2)


if __name__ == "__main__":
    unittest.main()
