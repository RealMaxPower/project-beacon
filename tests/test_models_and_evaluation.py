from __future__ import annotations

import unittest

from beacon.evaluation import evaluate_all, resolve_result
from beacon.models import AssertionSpec, EventRecorder, Scenario, ScenarioError


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
            "assertions": [
                {"id": "same", "type": "equals", "description": "one"},
                {"id": "same", "type": "equals", "description": "two"},
            ],
        }
        with self.assertRaises(ScenarioError):
            Scenario.from_dict(value)

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
