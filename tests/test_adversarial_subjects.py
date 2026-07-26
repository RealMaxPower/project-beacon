from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from beacon.adapters import JSONLCommandAdapter
from beacon.models import Scenario
from beacon.runner import run_scenario


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples" / "subjects" / "manifest.json"
DEFAULT_TIMEOUT = 15.0


def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _run(case: dict[str, Any], scenario_path: Path, directory: str) -> Any:
    adapter = JSONLCommandAdapter(
        [sys.executable, str(ROOT / case["script"])],
        timeout_seconds=float(case.get("timeout_seconds", DEFAULT_TIMEOUT)),
    )
    return run_scenario(
        Scenario.load(scenario_path),
        adapter,
        output_dir=directory,
        run_id=case["id"],
    )


class AdversarialSubjectTests(unittest.TestCase):
    """
    Drives every subject in the manifest against the starter scenario.

    The manifest records both the verdict Beacon *should* return and the one it
    returns *today*. These tests assert today's behavior, so they stay green
    while the known defects are open — and go red the moment a defect is fixed,
    which is the prompt to update `currently` and clear `defect`.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = _manifest()
        cls.scenario_path = ROOT / cls.manifest["scenario"]

    def test_every_run_produces_an_evidence_bundle(self) -> None:
        """
        The invariant that outranks every verdict: a run that writes no
        evidence is a bug in Beacon, whatever the subject did.
        """
        with tempfile.TemporaryDirectory() as directory:
            for case in self.manifest["subjects"]:
                with self.subTest(subject=case["id"]):
                    outcome = _run(case, self.scenario_path, directory)
                    self.assertTrue(outcome.json_path.exists())
                    self.assertTrue(outcome.markdown_path.exists())
                    self.assertIn(
                        outcome.evidence.result,
                        {"PASS", "FAIL", "INCOMPLETE"},
                    )

    def test_subjects_produce_their_recorded_verdicts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for case in self.manifest["subjects"]:
                with self.subTest(subject=case["id"]):
                    outcome = _run(case, self.scenario_path, directory)
                    self.assertEqual(
                        outcome.evidence.result,
                        case["currently"],
                        f"{case['id']} changed behavior. If this is a fix, "
                        f"update 'currently' in manifest.json and clear "
                        f"'defect'.",
                    )

    def test_manifest_defects_match_the_recorded_verdicts(self) -> None:
        """A defect note and a wrong verdict must always travel together."""
        for case in self.manifest["subjects"]:
            with self.subTest(subject=case["id"]):
                wrong = case["currently"] != case["should_be"]
                if wrong:
                    self.assertTrue(
                        case["defect"],
                        f"{case['id']} returns the wrong verdict but records "
                        f"no defect.",
                    )
                else:
                    self.assertIsNone(
                        case["defect"],
                        f"{case['id']} returns the right verdict but still "
                        f"records a defect.",
                    )

    def test_a_completed_subject_that_hangs_is_not_a_pass(self) -> None:
        """
        Spot-check the central invariant directly rather than through the
        manifest: every assertion passes, and the verdict is still INCOMPLETE.
        """
        case = next(
            item
            for item in self.manifest["subjects"]
            if item["id"] == "never_completes"
        )
        with tempfile.TemporaryDirectory() as directory:
            outcome = _run(case, self.scenario_path, directory)
        self.assertTrue(all(item["passed"] for item in outcome.evidence.assertions))
        self.assertEqual(outcome.evidence.result, "INCOMPLETE")

    def test_manifest_scripts_exist(self) -> None:
        for case in self.manifest["subjects"]:
            with self.subTest(subject=case["id"]):
                self.assertTrue((ROOT / case["script"]).is_file())


if __name__ == "__main__":
    unittest.main()
