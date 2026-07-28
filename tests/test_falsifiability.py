from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from beacon.adapters import JSONLCommandAdapter
from beacon.models import Scenario
from beacon.runner import run_scenario


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples" / "subjects" / "manifest.json"


HARNESS_ASSERTIONS = frozenset(
    {
        # Failing these produces INCOMPLETE rather than FAIL, and the runner's
        # failure-matrix tests already cover every way a subject can fail to
        # finish. An adversarial subject cannot make them FAIL by behaving
        # badly, only by not running.
        "task-completed",
        "answered-at-all",
        # Enforced by the usage recorder, which has its own tests. A subject
        # cannot exceed a budget the harness stops it from exceeding.
        "within-call-budget",
    }
)
"""
Assertions exempt from needing a subject that breaks them.

Kept deliberately short and explicit. The temptation with a check like this is
to widen the exemption until it passes, which converts a real guarantee into a
list of excuses.
"""


def _failed_assertions(script: str, scenario_path: Path) -> set[str]:
    with tempfile.TemporaryDirectory() as directory:
        outcome = run_scenario(
            Scenario.load(scenario_path),
            JSONLCommandAdapter(["python3", str(ROOT / script)]),
            output_dir=directory,
            run_id="falsify",
        )
    return {
        item["id"] for item in outcome.evidence.assertions if not item["passed"]
    }


class FalsifiabilityTests(unittest.TestCase):
    """
    Every behavioural assertion must have a subject that makes it fail.

    CONTRIBUTING has required this since the first release and the project
    still shipped assertions nothing could break — two in the starter scenario
    at the beginning, and `messages-preserved` later, which became
    unfalsifiable as a *side effect* of correctly removing a tool that was a
    trap. Both times the prose rule was in place and both times it was missed,
    because nobody was running the check. This runs it.

    What an unfalsifiable assertion costs: report.md prints its description as
    a finding. "Original messages were preserved" reads as a safety result
    when no tool on the surface could have altered a message.
    """

    @classmethod
    def setUpClass(cls) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        default = manifest["scenario"]
        cls.broken: dict[str, set[str]] = {}
        for case in manifest["subjects"]:
            path = case.get("scenario", default)
            cls.broken.setdefault(path, set())
            cls.broken[path] |= _failed_assertions(case["script"], ROOT / path)

    def test_every_behavioural_assertion_has_a_subject_that_breaks_it(self) -> None:
        for path in sorted(self.broken):
            scenario = Scenario.load(ROOT / path)
            declared = {item.id for item in scenario.assertions}
            unproven = sorted(declared - self.broken[path] - HARNESS_ASSERTIONS)
            with self.subTest(scenario=scenario.id):
                self.assertEqual(
                    unproven,
                    [],
                    f"{scenario.id}: no subject makes these fail, so the "
                    f"report states them without having tested them",
                )

    def test_every_shipped_scenario_is_covered_by_the_manifest(self) -> None:
        """
        A scenario with no adversarial subject at all is the easy way to pass
        the check above without having earned it.
        """
        shipped = {
            f"scenarios/{path.parent.name}/scenario.json"
            for path in (ROOT / "scenarios").glob("*/scenario.json")
        }
        self.assertEqual(shipped - set(self.broken), set())

    def test_the_exemption_list_is_not_quietly_growing(self) -> None:
        """
        Pins the exemptions by name. Widening this set is how a guarantee
        turns into a formality, so it should take a deliberate edit and show
        up in review.
        """
        self.assertEqual(
            HARNESS_ASSERTIONS,
            frozenset({"task-completed", "answered-at-all", "within-call-budget"}),
        )

    def test_each_exempt_assertion_really_is_a_harness_property(self) -> None:
        """An exemption is only honest if the assertion exists somewhere."""
        declared: set[str] = set()
        for path in (ROOT / "scenarios").glob("*/scenario.json"):
            declared |= {item.id for item in Scenario.load(path).assertions}
        self.assertEqual(HARNESS_ASSERTIONS - declared, set())


class CitationDesignTests(unittest.TestCase):
    """
    A `cites` assertion whose corroborating token sits inside the reference is
    satisfied by naming the reference — the name-drop the type exists to
    reject. Two shipped assertions had this, caught by a subject that listed
    every document path and read none of them.
    """

    def test_no_corroborating_token_hides_inside_its_own_reference(self) -> None:
        for path in sorted((ROOT / "scenarios").glob("*/scenario.json")):
            scenario = Scenario.load(path)
            for item in scenario.assertions:
                if item.type != "cites":
                    continue
                reference = str(item.expected["id"]).casefold()
                with self.subTest(scenario=scenario.id, assertion=item.id):
                    inside = [
                        token
                        for token in item.expected["near"]
                        if str(token).casefold() in reference
                    ]
                    self.assertEqual(inside, [])


if __name__ == "__main__":
    unittest.main()
