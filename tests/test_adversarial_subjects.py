from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

import sys as _sys
from pathlib import Path as _Path

# `unittest discover -s tests` puts this directory on the path; running a
# module directly as `python3 -m unittest tests.test_x` does not. Both forms
# get used, so make the sibling import work either way.
_sys.path.insert(0, str(_Path(__file__).resolve().parent))

from _subject_runs import run_subject


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples" / "subjects" / "manifest.json"


def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _run(case: dict[str, Any], scenario_path: Path) -> Any:
    """
    This subject's run, shared with every other harness that asks for it.

    The bundles live in one process-wide evidence directory rather than a
    per-test one, so a bundle is still on disk when a later test looks for it.
    """
    scenario = ROOT / case.get("scenario", str(scenario_path))
    return run_subject(case, scenario)


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
        for case in self.manifest["subjects"]:
            with self.subTest(subject=case["id"]):
                outcome = _run(case, self.scenario_path)
                self.assertTrue(outcome.json_path.exists())
                self.assertTrue(outcome.markdown_path.exists())
                self.assertIn(
                    outcome.evidence.result,
                    {"PASS", "FAIL", "INCOMPLETE"},
                )

    def test_subjects_produce_their_recorded_verdicts(self) -> None:
        for case in self.manifest["subjects"]:
            with self.subTest(subject=case["id"]):
                outcome = _run(case, self.scenario_path)
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
        manifest: the subject does the work, so every assertion about what it
        *did* passes, and the verdict is still INCOMPLETE because it never said
        it was finished.

        `task-completed` is excluded, and the exclusion is the point rather
        than a loophole. It asserts on `subject.status`, so it is a statement
        about the ending rather than about the work, and a subject that hangs
        fails it for the same reason the run is INCOMPLETE. Counting it here
        would make the check pass for a second reason and stop proving the
        first — that a full set of satisfied behavioural assertions still does
        not add up to a PASS.
        """
        case = next(
            item
            for item in self.manifest["subjects"]
            if item["id"] == "never_completes"
        )
        outcome = _run(case, self.scenario_path)
        behavioural = [
            item
            for item in outcome.evidence.assertions
            if item["id"] != "task-completed"
        ]
        self.assertTrue(behavioural, "nothing left to check once the ending is dropped")
        self.assertTrue(all(item["passed"] for item in behavioural))
        self.assertEqual(outcome.evidence.result, "INCOMPLETE")

    def test_manifest_scripts_exist(self) -> None:
        for case in self.manifest["subjects"]:
            with self.subTest(subject=case["id"]):
                self.assertTrue((ROOT / case["script"]).is_file())

    def test_no_subject_is_left_out_of_the_manifest(self) -> None:
        """
        A subject nobody runs proves nothing. Adding one to the directory and
        forgetting the manifest entry is silent otherwise.
        """
        directory = ROOT / "examples" / "subjects"
        on_disk = {
            path.name
            for path in directory.glob("*.py")
            if not path.name.startswith("_") and path.name != "run_suite.py"
        }
        listed = {Path(case["script"]).name for case in self.manifest["subjects"]}
        # leaks_its_key.py is driven by tests/test_secrets.py instead: it needs
        # BEACON_CANARY_SECRET in the environment, and its exfiltration draft
        # would fail this scenario for reasons unrelated to what it tests.
        expected_unlisted = {"leaks_its_key.py"}
        self.assertEqual(on_disk - listed, expected_unlisted)


if __name__ == "__main__":
    unittest.main()
