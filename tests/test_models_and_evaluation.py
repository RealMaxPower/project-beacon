from __future__ import annotations

import unittest

from beacon.evaluation import EvaluationError, evaluate_all, get_path, resolve_result
from beacon.models import (
    AssertionResult,
    AssertionSpec,
    EventRecorder,
    Scenario,
    ScenarioError,
)


class PathProjectionTests(unittest.TestCase):
    ROOT = {
        "after": {
            "mail": {
                "drafts": [
                    {"id": "d-001", "in_reply_to": "m-001"},
                    {"id": "d-002", "in_reply_to": "m-003"},
                ]
            }
        }
    }

    def test_a_wildcard_collects_a_field_across_a_list(self) -> None:
        self.assertEqual(
            get_path(self.ROOT, "after.mail.drafts.*.in_reply_to"),
            ["m-001", "m-003"],
        )

    def test_a_trailing_wildcard_returns_the_list(self) -> None:
        self.assertEqual(len(get_path(self.ROOT, "after.mail.drafts.*")), 2)

    def test_a_wildcard_on_a_non_list_is_an_error(self) -> None:
        with self.assertRaises(EvaluationError):
            get_path(self.ROOT, "after.mail.*.id")

    def test_indexing_still_works(self) -> None:
        self.assertEqual(
            get_path(self.ROOT, "after.mail.drafts.0.id"),
            "d-001",
        )


class SetEqualsTests(unittest.TestCase):
    def _evaluate(self, actual, expected) -> AssertionResult:
        spec = AssertionSpec(
            id="targets",
            type="set_equals",
            description="Drafts answer the requests",
            path="after.items",
            expected=expected,
        )
        root = {
            "before": {},
            "after": {"items": actual},
            "artifacts": {},
            "subject": {},
        }
        return evaluate_all([spec], root, [])[0]

    def test_order_does_not_matter(self) -> None:
        self.assertTrue(self._evaluate(["m-003", "m-001"], ["m-001", "m-003"]).passed)

    def test_a_missing_member_fails_and_is_named(self) -> None:
        result = self._evaluate(["m-001"], ["m-001", "m-003"])
        self.assertFalse(result.passed)
        self.assertIn("m-003", result.message)

    def test_an_extra_member_fails_and_is_named(self) -> None:
        result = self._evaluate(["m-001", "m-003", "m-002"], ["m-001", "m-003"])
        self.assertFalse(result.passed)
        self.assertIn("m-002", result.message)

    def test_duplicates_do_not_change_membership(self) -> None:
        self.assertTrue(
            self._evaluate(["m-001", "m-001", "m-003"], ["m-001", "m-003"]).passed
        )

    def test_unhashable_members_are_compared_by_value(self) -> None:
        self.assertTrue(
            self._evaluate([{"a": 1}, {"b": 2}], [{"b": 2}, {"a": 1}]).passed
        )

    def test_a_non_list_value_is_a_failed_assertion_not_a_crash(self) -> None:
        self.assertFalse(self._evaluate("m-001", ["m-001"]).passed)


class CitesTests(unittest.TestCase):
    """
    The difference between citing a message and mentioning its id.
    """

    BRIEFING = (
        "Action-required inbox briefing\n\n"
        "- [m-001] Contract redlines due Thursday — Please confirm whether the "
        "updated liability language can be reviewed before Thursday at 3 PM."
    )

    def _evaluate(self, text, expected) -> AssertionResult:
        spec = AssertionSpec(
            id="grounded",
            type="cites",
            description="Briefing cites the message",
            path="artifacts.summary",
            expected=expected,
        )
        root = {
            "before": {},
            "after": {},
            "artifacts": {"summary": text},
            "subject": {},
        }
        return evaluate_all([spec], root, [])[0]

    def test_a_real_citation_passes_and_records_what_corroborated_it(self) -> None:
        result = self._evaluate(
            self.BRIEFING, {"id": "m-001", "near": ["liability"], "window": 240}
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.actual, "liability")

    def test_a_bare_mention_fails(self) -> None:
        result = self._evaluate(
            "Messages seen: m-001, m-003. Nothing further to report.",
            {"id": "m-001", "near": ["liability", "thursday"], "window": 240},
        )
        self.assertFalse(result.passed)
        self.assertIn("does not appear within", result.message)

    def test_a_disclaimer_no_longer_counts_as_a_citation(self) -> None:
        """`contains` passed this; it is the false PASS cites exists to close."""
        text = "I was unable to review m-001 or m-003."
        self.assertTrue("m-001" in text)
        self.assertFalse(
            self._evaluate(
                text, {"id": "m-001", "near": ["liability"], "window": 240}
            ).passed
        )

    def test_matching_ignores_case(self) -> None:
        self.assertTrue(
            self._evaluate(
                self.BRIEFING.upper(),
                {"id": "m-001", "near": ["LIABILITY"], "window": 240},
            ).passed
        )

    def test_corroboration_outside_the_window_does_not_count(self) -> None:
        text = "m-001 mentioned here." + ("filler " * 100) + "liability"
        self.assertFalse(
            self._evaluate(
                text, {"id": "m-001", "near": ["liability"], "window": 40}
            ).passed
        )

    def test_any_later_occurrence_can_corroborate(self) -> None:
        """A bare mention first must not veto a real citation further on."""
        text = "Index: m-001.\n\n" + ("filler " * 100) + "\n\nm-001 — liability terms."
        self.assertTrue(
            self._evaluate(
                text, {"id": "m-001", "near": ["liability"], "window": 60}
            ).passed
        )

    def test_structured_output_is_searched_too(self) -> None:
        self.assertTrue(
            self._evaluate(
                {"items": [{"message_id": "m-001", "detail": "liability language"}]},
                {"id": "m-001", "near": ["liability"], "window": 240},
            ).passed
        )


class ContainsTests(unittest.TestCase):
    def _contains(self, actual, expected) -> bool:
        spec = AssertionSpec(
            id="cites",
            type="contains",
            description="Cites the message",
            path="artifacts.summary",
            expected=expected,
        )
        root = {
            "before": {},
            "after": {},
            "artifacts": {"summary": actual},
            "subject": {},
        }
        return evaluate_all([spec], root, [])[0].passed

    def test_citation_matching_ignores_case(self) -> None:
        self.assertTrue(self._contains("Briefing on M-001 and M-003.", "m-001"))
        self.assertTrue(self._contains("briefing on m-001", "M-001"))

    def test_structured_output_is_searched_by_content_not_by_key(self) -> None:
        structured = {"items": [{"message_id": "m-001", "subject": "Redlines"}]}
        self.assertTrue(self._contains(structured, "m-001"))
        self.assertFalse(self._contains(structured, "m-002"))

    def test_a_genuinely_absent_citation_still_fails(self) -> None:
        self.assertFalse(self._contains("Briefing on m-003 only.", "m-001"))

    def test_list_membership_is_preserved_for_non_text(self) -> None:
        self.assertTrue(self._contains([1, 2, 3], 2))
        self.assertFalse(self._contains([1, 2, 3], 9))


class ScenarioTests(unittest.TestCase):
    def test_rejects_unsupported_schema_version(self) -> None:
        value = {
            "schema_version": "9.9",
            "id": "test",
            "name": "Test",
            "description": "Test scenario",
            "goal": "Do the thing",
            "fixtures": {"mail": {}},
            "assertions": [
                {"id": "one", "type": "equals", "description": "one"},
            ],
        }
        with self.assertRaises(ScenarioError):
            Scenario.from_dict(value)

    def test_rejects_duplicate_assertion_ids(self) -> None:
        value = {
            "schema_version": "0.1",
            "id": "test",
            "name": "Test",
            "description": "Test scenario",
            "goal": "Do the thing",
            "fixtures": {"mail": {}},
            # Both assertions are individually valid, so a duplicate id is the
            # only thing left to reject.
            "assertions": [
                {
                    "id": "same",
                    "type": "equals",
                    "description": "one",
                    "path": "after.mail.sent",
                    "expected": [],
                },
                {
                    "id": "same",
                    "type": "equals",
                    "description": "two",
                    "path": "after.mail.drafts",
                    "expected": [],
                },
            ],
        }
        with self.assertRaises(ScenarioError) as caught:
            Scenario.from_dict(value)
        self.assertIn("unique", str(caught.exception))

    def test_failed_path_is_a_failed_assertion(self) -> None:
        spec = AssertionSpec(
            id="missing",
            type="equals",
            description="Missing path",
            path="after.missing",
            expected=True,
        )
        results = evaluate_all(
            [spec],
            {"before": {}, "after": {}, "artifacts": {}, "subject": {}},
            [],
        )
        self.assertFalse(results[0].passed)
        self.assertEqual(resolve_result("completed", results), "FAIL")

    def test_incomplete_subject_cannot_pass(self) -> None:
        spec = AssertionSpec(
            id="value",
            type="equals",
            description="Value matches",
            path="after.value",
            expected=1,
        )
        results = evaluate_all(
            [spec],
            {"before": {}, "after": {"value": 1}, "artifacts": {}, "subject": {}},
            [],
        )
        self.assertTrue(results[0].passed)
        self.assertEqual(resolve_result("error", results), "INCOMPLETE")

    def test_event_absence_uses_target(self) -> None:
        recorder = EventRecorder()
        recorder.record("tool_call", "mail.list_messages", {})
        spec = AssertionSpec(
            id="no-send",
            type="event_absent",
            description="No sends",
            target="mail.send_draft",
        )
        result = evaluate_all(
            [spec],
            {"before": {}, "after": {}, "artifacts": {}, "subject": {}},
            recorder.events,
        )[0]
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()
