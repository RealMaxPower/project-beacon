from __future__ import annotations

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
        state={"before_digest": "digest-before", "after_digest": after_digest},
        state_diff={"change_count": 0, "changes": []},
        events=[
            {"sequence": index, "kind": "tool_call", "target": target}
            for index, target in enumerate(tool_targets, start=1)
        ],
        artifacts=artifacts if artifacts is not None else {"summary": "text"},
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
                _evidence(result="PASS", after_digest="digest-x"),
                _evidence(result="FAIL", after_digest="digest-y"),
            ]
        )
        self.assertFalse(report.stable)
        self.assertIn("result", report.divergent_fields)
        self.assertIn("after_digest", report.divergent_fields)
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


if __name__ == "__main__":
    unittest.main()
