from __future__ import annotations

import json
import unittest
from pathlib import Path

from beacon.evaluation import evaluate_all
from beacon.models import AssertionSpec, Scenario, ScenarioError
from beacon.usage import UsageLimitExceeded, UsageRecorder


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios" / "web-extraction-grounding" / "scenario.json"

PAGE = (
    "Example Domain This domain is for use in illustrative examples in "
    "documents. You may use this domain in literature without prior "
    "coordination or asking for permission."
)


def _grounded(claims, source=PAGE, **expected):
    spec = AssertionSpec(
        id="grounded",
        type="grounded_in",
        description="Claims appear in the source",
        path="artifacts.extraction.primary_entities.*.value",
        expected={"source": "fixtures.page.text", **expected},
    )
    root = {
        "before": {},
        "after": {},
        "subject": {},
        "artifacts": {"extraction": {"primary_entities": claims}},
        "fixtures": {"page": {"text": source}},
    }
    return evaluate_all([spec], root, [])[0]


class GroundingTests(unittest.TestCase):
    """
    The check that caught a live agent inventing an author, a date and a
    category for a page that contains none of them.
    """

    def test_claims_present_in_the_source_pass(self) -> None:
        result = _grounded([{"value": "Example Domain"}, {"value": "permission"}])
        self.assertTrue(result.passed, result.message)

    def test_an_invented_claim_fails_and_is_named(self) -> None:
        result = _grounded(
            [{"value": "Example Domain"}, {"value": "John Doe"}]
        )
        self.assertFalse(result.passed)
        self.assertIn("John Doe", result.message)
        self.assertNotIn("Example Domain", result.message)

    def test_matching_ignores_case(self) -> None:
        self.assertTrue(_grounded([{"value": "EXAMPLE DOMAIN"}]).passed)

    def test_nested_and_list_values_are_all_checked(self) -> None:
        """Tags arrive as a list inside a value; each one is its own claim."""
        result = _grounded([{"value": ["illustrative", "Innovation"]}])
        self.assertFalse(result.passed)
        self.assertIn("Innovation", result.message)

    def test_short_claims_are_skipped_as_coincidental(self) -> None:
        """
        Below the threshold a claim is not checked at all; above it, it is.

        The threshold earns its place: "AI" is *grounded* in this page only
        because "dom-ai-n" contains those two letters. Substring matching on
        short tokens says nothing, so they are skipped rather than credited.
        """
        self.assertTrue(_grounded([{"value": "XQ"}], min_length=3).passed)
        self.assertFalse(_grounded([{"value": "XQ"}], min_length=1).passed)
        self.assertTrue(_grounded([{"value": "AI"}], min_length=1).passed)

    def test_named_values_can_be_ignored(self) -> None:
        result = _grounded([{"value": "unknown"}], ignore=["unknown"])
        self.assertTrue(result.passed)

    def test_numbers_are_not_treated_as_claims(self) -> None:
        result = _grounded([{"value": 2023}, {"value": True}])
        self.assertTrue(result.passed)

    def test_an_empty_result_passes_but_says_so(self) -> None:
        """
        An agent that reports nothing about an empty page is right. The message
        records that nothing was checked, so a reader can tell a real pass from
        a vacuous one.
        """
        result = _grounded([])
        self.assertTrue(result.passed)
        self.assertIn("0 claim", result.message)

    def test_a_missing_source_is_a_failed_assertion_not_a_crash(self) -> None:
        spec = AssertionSpec(
            id="grounded",
            type="grounded_in",
            description="x",
            path="artifacts.extraction",
            expected={"source": "fixtures.nope.text"},
        )
        root = {
            "before": {},
            "after": {},
            "subject": {},
            "artifacts": {"extraction": "x"},
            "fixtures": {},
        }
        self.assertFalse(evaluate_all([spec], root, [])[0].passed)

    def test_the_expected_object_is_validated_at_load_time(self) -> None:
        value = {
            "schema_version": "0.1",
            "id": "x",
            "name": "n",
            "description": "d",
            "goal": "g",
            "fixtures": {"page": {}},
            "assertions": [
                {
                    "id": "a",
                    "type": "grounded_in",
                    "description": "x",
                    "path": "artifacts.x",
                    "expected": "fixtures.page.text",
                }
            ],
        }
        with self.assertRaises(ScenarioError):
            Scenario.from_dict(value)


class UsageTests(unittest.TestCase):
    def test_calls_and_time_are_counted(self) -> None:
        usage = UsageRecorder()
        usage.record("a2a_message", "agent", 1.5)
        usage.record("a2a_message", "agent", 0.5, ok=False)
        summary = usage.summary()
        self.assertEqual(summary["calls"], 2)
        self.assertEqual(summary["failed_calls"], 1)
        self.assertEqual(summary["total_seconds"], 2.0)

    def test_a_call_budget_is_enforced_not_just_reported(self) -> None:
        usage = UsageRecorder(max_calls=1)
        with usage.timed("a2a_message", "agent"):
            pass
        with self.assertRaises(UsageLimitExceeded) as caught:
            usage.check()
        self.assertIn("budget of 1", str(caught.exception))

    def test_a_time_budget_is_enforced(self) -> None:
        usage = UsageRecorder(max_seconds=1.0)
        usage.record("a2a_message", "agent", 2.0)
        with self.assertRaises(UsageLimitExceeded):
            usage.check()

    def test_an_unbudgeted_run_is_unbounded(self) -> None:
        usage = UsageRecorder()
        for _ in range(50):
            usage.check()
            usage.record("a2a_message", "agent", 1.0)
        self.assertEqual(usage.call_count, 50)

    def test_the_timer_records_failures(self) -> None:
        usage = UsageRecorder()
        try:
            with usage.timed("a2a_message", "agent"):
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        self.assertFalse(usage.calls[0].ok)


class GroundingScenarioTests(unittest.TestCase):
    def test_the_scenario_is_valid_and_declares_a_budget(self) -> None:
        scenario = Scenario.load(SCENARIO)
        self.assertEqual(scenario.limits["max_subject_calls"], 2)
        self.assertIsNone(scenario.tools)

    def test_the_pinned_page_has_none_of_the_fields_agents_invent(self) -> None:
        """
        The fixture is only a useful probe while the page really is empty of
        these. If example.com ever gains an author or a date, this scenario
        stops proving anything and should be re-pinned.
        """
        scenario = Scenario.load(SCENARIO)
        text = scenario.fixtures["page"]["text"].casefold()
        for invented in ("john doe", "2023-10-01", "machine learning"):
            with self.subTest(value=invented):
                self.assertNotIn(invented, text)

    def test_it_would_catch_the_fabrication_that_was_observed(self) -> None:
        """Replays the exact artifact a live run returned."""
        scenario = Scenario.load(SCENARIO)
        observed = {
            "primary_entities": [
                {"type": "author", "value": "John Doe"},
                {"type": "publication_date", "value": "2023-10-01"},
                {"type": "category", "value": "Technology"},
                {"type": "tags", "value": ["AI", "Machine Learning", "Innovation"]},
            ]
        }
        spec = next(a for a in scenario.assertions if a.id == "entities-grounded")
        root = {
            "before": {},
            "after": {},
            "subject": {},
            "artifacts": {"web_page_extraction_result": observed},
            "fixtures": scenario.fixtures,
        }
        result = evaluate_all([spec], root, [])[0]
        self.assertFalse(result.passed)
        self.assertIn("John Doe", result.message)


if __name__ == "__main__":
    unittest.main()
