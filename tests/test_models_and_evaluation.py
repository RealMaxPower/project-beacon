from __future__ import annotations

import unittest

from beacon.evaluation import evaluate_all, resolve_result
from beacon.models import AssertionSpec, EventRecorder, Scenario, ScenarioError


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
