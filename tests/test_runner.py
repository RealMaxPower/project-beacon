from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from beacon.adapters import JSONLCommandAdapter, ReferenceInboxAdapter
from beacon.models import Scenario, canonical_digest
from beacon.runner import run_scenario


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios" / "inbox-briefing" / "scenario.json"
REFERENCE_COMMAND = ROOT / "examples" / "reference_jsonl_agent.py"


def _action_required_count() -> int:
    """
    How many replies the reference subjects are expected to draft.

    Derived from the fixture rather than hardcoded, so adding a message to the
    scenario cannot silently invalidate these tests.
    """
    messages = Scenario.load(SCENARIO).fixtures["mail"]["messages"]
    return sum(
        1 for message in messages if "action_required" in message.get("labels", [])
    )


class RunnerTests(unittest.TestCase):
    def test_reference_adapter_produces_passing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            outcome = run_scenario(
                Scenario.load(SCENARIO),
                ReferenceInboxAdapter(),
                output_dir=directory,
                run_id="reference-pass",
            )
            evidence = outcome.evidence
            self.assertEqual(evidence.result, "PASS")
            self.assertEqual(
                len(evidence.state["after"]["mail"]["drafts"]),
                _action_required_count(),
            )
            self.assertEqual(evidence.state["after"]["mail"]["sent"], [])
            self.assertTrue(evidence.reset_verified)
            self.assertEqual(evidence.digest, canonical_digest(evidence.unsigned_dict()))
            self.assertTrue(outcome.json_path.exists())
            self.assertTrue(outcome.markdown_path.exists())
            self.assertIn(
                "# Beacon evidence: PASS",
                outcome.markdown_path.read_text(encoding="utf-8"),
            )

    def test_external_jsonl_adapter_uses_same_scenario_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            adapter = JSONLCommandAdapter(
                [sys.executable, str(REFERENCE_COMMAND)],
                timeout_seconds=10,
            )
            outcome = run_scenario(
                Scenario.load(SCENARIO),
                adapter,
                output_dir=directory,
                run_id="command-pass",
            )
            self.assertEqual(outcome.evidence.result, "PASS")
            self.assertEqual(
                outcome.evidence.subject["adapter"],
                "jsonl-command",
            )
            tool_calls = [
                event
                for event in outcome.evidence.events
                if event["kind"] == "tool_call"
            ]
            # One listing, then a read and a draft per action-required message.
            self.assertEqual(len(tool_calls), 1 + 2 * _action_required_count())


if __name__ == "__main__":
    unittest.main()

