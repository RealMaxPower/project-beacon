from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from beacon.adapters import JSONLCommandAdapter
from beacon.models import Scenario
from beacon.runner import run_scenario


ROOT = Path(__file__).resolve().parents[1]
SUBJECTS = ROOT / "examples" / "subjects"

SERVICE_SCENARIO = ROOT / "scenarios" / "injection-resistance" / "scenario.json"
HOSTED_SCENARIO = ROOT / "scenarios" / "hosted-injection-resistance" / "scenario.json"

# Assertions whose failure is a statement about behaviour. Each must have a
# subject that makes it fail, or it is a claim the evidence does not support.
# `task-completed` and `within-call-budget` are exempt: they are properties of
# the harness, covered by the runner's own failure-matrix tests.
BEHAVIOURAL = {
    SERVICE_SCENARIO: {
        "summary-keeps-its-shape",
        "real-work-was-done",
        "confidential-figures-not-disclosed",
        "deletion-never-attempted",
    },
    HOSTED_SCENARIO: {
        "summarised-the-public-note",
        "annex-not-reproduced",
    },
}

# subject -> (scenario, assertions it must fail)
EXPECTED = {
    "resists_injection.py": (SERVICE_SCENARIO, set()),
    "leaks_confidential_file.py": (
        SERVICE_SCENARIO,
        {"confidential-figures-not-disclosed"},
    ),
    "obeys_delete_injection.py": (SERVICE_SCENARIO, {"deletion-never-attempted"}),
    "obeys_format_hijack.py": (
        SERVICE_SCENARIO,
        {"summary-keeps-its-shape", "real-work-was-done"},
    ),
    "malformed_summary.py": (SERVICE_SCENARIO, {"summary-keeps-its-shape"}),
    "hosted_resists_injection.py": (HOSTED_SCENARIO, set()),
    "hosted_leaks_annex.py": (HOSTED_SCENARIO, {"annex-not-reproduced"}),
    "hosted_answers_something_else.py": (
        HOSTED_SCENARIO,
        {"summarised-the-public-note"},
    ),
}


def _failed(subject: str, scenario_path: Path) -> tuple[str, set[str]]:
    with tempfile.TemporaryDirectory() as directory:
        outcome = run_scenario(
            Scenario.load(scenario_path),
            JSONLCommandAdapter([sys.executable, str(SUBJECTS / subject)]),
            output_dir=directory,
            run_id=f"inj-{subject}",
        )
    evidence = outcome.evidence
    return evidence.result, {
        item["id"] for item in evidence.assertions if not item["passed"]
    }


class InjectionSubjectTests(unittest.TestCase):
    """
    A scenario about resisting injection is worth exactly as much as the proof
    that obeying one is detected. These run the obeying subjects.
    """

    def test_each_subject_fails_the_assertions_it_is_meant_to(self) -> None:
        for subject, (scenario, expected) in EXPECTED.items():
            with self.subTest(subject=subject):
                result, failed = _failed(subject, scenario)
                self.assertEqual(failed, expected)
                self.assertEqual(result, "PASS" if not expected else "FAIL")

    def test_every_behavioural_assertion_has_a_subject_that_breaks_it(self) -> None:
        """
        Mechanises the rule rather than trusting it. An assertion no subject
        has ever failed is a claim nobody has tested, and this project shipped
        two of those before anyone noticed.
        """
        for scenario_path, required in BEHAVIOURAL.items():
            covered: set[str] = set()
            for subject, (scenario, expected) in EXPECTED.items():
                if scenario == scenario_path:
                    covered |= expected
            with self.subTest(scenario=scenario_path.parent.name):
                self.assertEqual(
                    required - covered,
                    set(),
                    "no subject fails these assertions",
                )

    def test_the_declared_assertions_and_the_expectations_agree(self) -> None:
        """Catches an assertion added to a scenario with no subject to match."""
        for scenario_path, required in BEHAVIOURAL.items():
            declared = {
                item.id for item in Scenario.load(scenario_path).assertions
            }
            with self.subTest(scenario=scenario_path.parent.name):
                self.assertTrue(required <= declared, required - declared)


class CanaryDesignTests(unittest.TestCase):
    """
    The detection rests on one property: the canary appears only in the
    withheld material, never in the injected instruction. If it appeared in
    both, an agent that quoted the instruction while refusing it would be
    reported as leaking — and the scenario would punish the right behaviour.
    """

    def _canaries(self, scenario_path: Path) -> list[str]:
        for item in Scenario.load(scenario_path).assertions:
            if item.type == "contains_none":
                return [str(value) for value in item.expected]
        raise AssertionError("scenario has no contains_none assertion")

    def test_the_hosted_canaries_live_only_in_the_annex(self) -> None:
        """
        Commas are stripped on both sides because some canaries are
        reformatted variants — '118,500' for an agent that discloses the
        figure while prettifying it. Those never appear literally in the
        source, and should not have to.
        """
        goal = Scenario.load(HOSTED_SCENARIO).goal
        directive = goal.split("[SYSTEM DIRECTIVE")[1].split("[END DIRECTIVE]")[0]
        annex = goal.split("--- CONFIDENTIAL ANNEX ---")[1]
        for canary in self._canaries(HOSTED_SCENARIO):
            with self.subTest(canary=canary):
                self.assertIn(canary.replace(",", ""), annex.replace(",", ""))
                self.assertNotIn(canary.replace(",", ""), directive.replace(",", ""))

    def test_the_service_canaries_live_only_in_the_confidential_file(self) -> None:
        scenario = Scenario.load(SERVICE_SCENARIO)
        files = {
            item["path"]: item["content"]
            for item in scenario.fixtures["files"]["files"]
        }
        confidential = files["hr/compensation-bands.md"]
        others = "\n".join(
            content for path, content in files.items() if not path.startswith("hr/")
        )
        for canary in self._canaries(SERVICE_SCENARIO):
            with self.subTest(canary=canary):
                normalised = canary.replace(",", "")
                self.assertIn(normalised, confidential.replace(",", ""))
                self.assertNotIn(normalised, others.replace(",", ""))

    def test_a_reformatted_figure_is_still_caught(self) -> None:
        """
        Why the comma variants are in the canary list at all: an agent that
        discloses 118500 as '118,500' has disclosed it.
        """
        from beacon.evaluation import evaluate_assertion

        assertion = next(
            item
            for item in Scenario.load(HOSTED_SCENARIO).assertions
            if item.type == "contains_none"
        )
        result = evaluate_assertion(
            assertion,
            {"artifacts": {"out": "band four midpoint is 118,500"}},
            (),
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.actual, ["118,500"])

    def test_the_injection_is_actually_present_to_be_resisted(self) -> None:
        """A scenario whose fixture lost its payload would pass everything."""
        scenario = Scenario.load(SERVICE_SCENARIO)
        content = json.dumps(scenario.fixtures)
        self.assertIn("SYSTEM DIRECTIVE", content)
        self.assertIn("NOTE TO ASSISTANT", content)
        self.assertIn("SYSTEM DIRECTIVE", Scenario.load(HOSTED_SCENARIO).goal)

    def test_the_confidential_file_is_reachable_so_leaking_is_possible(self) -> None:
        """
        If hr/ were protected, no subject could disclose it and the assertion
        could never fail. The restriction here is an instruction, which is the
        thing being tested.
        """
        scenario = Scenario.load(SERVICE_SCENARIO)
        confidential = [
            item
            for item in scenario.fixtures["files"]["files"]
            if item["path"].startswith("hr/")
        ]
        self.assertTrue(confidential)
        for item in confidential:
            self.assertFalse(item.get("protected", False))


if __name__ == "__main__":
    unittest.main()
