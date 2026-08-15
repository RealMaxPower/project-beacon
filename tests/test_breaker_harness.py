from __future__ import annotations

import json
import unittest
from pathlib import Path

import sys as _sys
from pathlib import Path as _Path

# `unittest discover -s tests` puts this directory on the path; running a
# module directly as `python3 -m unittest tests.test_x` does not. Both forms
# get used, so make the sibling import work either way.
_sys.path.insert(0, str(_Path(__file__).resolve().parent))

from _subject_runs import failed_assertions, subject_args


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples" / "subjects" / "manifest.json"
SUBJECTS = ROOT / "examples" / "subjects"


#: Each breaker-driven entry, and the hand-written subject it stands in for.
#:
#: This is the acceptance test for the whole design. The claim being made is
#: not that the driver produces *a* failure but that it produces the *same*
#: failure — otherwise the forty-eight scenarios still to be written would be
#: measured by something subtly different from what the seven existing ones
#: were, and nobody would find out until a verdict disagreed.
EQUIVALENTS = {
    "br_deletes_documents": "deletes_documents",
    "br_tidies_by_renaming": "tidies_by_renaming",
    "br_skips_tagging": "skips_tagging",
    "br_index_without_evidence": "index_without_evidence",
    "br_control": "organizes_documents",
}


class BreakerEquivalenceTests(unittest.TestCase):
    """
    The declarative driver against the hand-written subjects it replaces.

    Forty-seven Python files for seven scenarios is about six per scenario, and
    every one is a competent baseline plus exactly one perturbation. At the ~55
    scenarios the taxonomy asks for, writing them by hand is two or three
    hundred near-copies — which does not just cost time, it shapes the suite
    around what is cheap to write instead of around what needs measuring.

    So baselines stay code, one per scenario, and perturbations become data.
    The hand-written subjects are kept rather than deleted: they are the
    empirical ground truth for the scenarios that already ship, and this
    comparison is worth more than a migration would have been.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = {
            case["id"]: case
            for case in json.loads(MANIFEST.read_text(encoding="utf-8"))["subjects"]
        }

    def _failures(self, subject_id: str) -> set[str]:
        case = self.cases[subject_id]
        return failed_assertions(case, ROOT / case["scenario"])

    def test_the_driver_breaks_exactly_what_the_handwritten_subject_breaks(self) -> None:
        for driven, handwritten in EQUIVALENTS.items():
            with self.subTest(subject=driven):
                self.assertEqual(
                    self._failures(driven),
                    self._failures(handwritten),
                    f"{driven} and {handwritten} disagree about which "
                    f"assertions fail; the driver is not a faithful stand-in",
                )

    def test_the_control_breaks_nothing(self) -> None:
        """
        A driver that failed the scenario would make every comparison above
        vacuously true — two subjects that both fail everything agree.
        """
        self.assertEqual(self._failures("br_control"), set())

    def test_each_driven_breaker_actually_breaks_something(self) -> None:
        for driven in EQUIVALENTS:
            if driven == "br_control":
                continue
            with self.subTest(subject=driven):
                self.assertTrue(self._failures(driven))


class BreakerWiringTests(unittest.TestCase):
    """The pieces the manifest guard cannot see, and the ones it must not."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = json.loads(MANIFEST.read_text(encoding="utf-8"))["subjects"]

    def test_a_driven_entry_names_a_plan_and_a_strategy(self) -> None:
        for case in self.cases:
            if Path(case["script"]).name != "breaker.py":
                continue
            with self.subTest(subject=case["id"]):
                self.assertIn("plan", case)
                self.assertIn("strategy", case)

    def test_every_named_plan_and_strategy_exists(self) -> None:
        _sys.path.insert(0, str(SUBJECTS))
        import _strategies

        for case in self.cases:
            if Path(case["script"]).name != "breaker.py":
                continue
            with self.subTest(subject=case["id"]):
                self.assertTrue((SUBJECTS / "plans" / f"{case['plan']}.py").is_file())
                self.assertIn(case["strategy"], _strategies.STRATEGIES)

    def test_a_driven_entry_is_launched_with_its_own_id(self) -> None:
        """
        One script serves many entries, so the id is the only thing telling it
        which one it is. A silent default here would run every driven entry as
        whichever plan happened to be first.
        """
        for case in self.cases:
            if Path(case["script"]).name != "breaker.py":
                continue
            with self.subTest(subject=case["id"]):
                self.assertEqual(subject_args(case), [case["id"]])

    def test_plans_are_not_mistaken_for_subjects(self) -> None:
        """
        `plans/` is a subdirectory, so the non-recursive glob in
        `test_adversarial_subjects.py` that requires every subject to be in the
        manifest does not see it — which is what lets one script and many plan
        modules coexist with a guard written for one file per subject.
        """
        directory = SUBJECTS
        top_level = {path.name for path in directory.glob("*.py")}
        self.assertNotIn("document_organization.py", top_level)
        self.assertTrue((directory / "plans" / "document_organization.py").is_file())


if __name__ == "__main__":
    unittest.main()
