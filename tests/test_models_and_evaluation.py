from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

from beacon.evaluation import EvaluationError, evaluate_all, get_path, resolve_result
from beacon.models import (
    AssertionResult,
    AssertionSpec,
    EventRecorder,
    Scenario,
    ScenarioError,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


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


class PublishedShapeTests(unittest.TestCase):
    """
    A scenario may not grade a shape it never showed the subject.

    `output_contract` is the only part of a scenario the subject is told, so a
    `conforms_to` on the contracted artifact is unmeetable unless the same
    schema is published there. Both web-extraction scenarios did exactly that,
    demanding six fields while the contract said only "Structured extraction of
    the page at the URL in the goal" — a shape that happened to be one hosted
    agent's native output, so they could grade that agent and nothing else. A
    real model answered in prose and was marked down for a schema nobody had
    shown it. Enabling this check found a third case in `injection-resistance`
    and a fourth in what `beacon init` generates.
    """

    SHAPE = {
        "type": "object",
        "required": ["value"],
        "properties": {"value": {"type": "string", "minLength": 1}},
    }

    def _scenario(self, contract: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": "0.1",
            "id": "shape-probe",
            "name": "Shape probe",
            "description": "d",
            "goal": "Return the thing.",
            "fixtures": {"page": {"text": "t"}},
            "output_contract": contract,
            "assertions": [
                {
                    "id": "keeps-its-shape",
                    "type": "conforms_to",
                    "path": "artifacts.report",
                    "expected": self.SHAPE,
                    "description": "The output has the shape asked for",
                }
            ],
        }

    def test_grading_a_shape_that_is_not_published_is_refused(self) -> None:
        value = self._scenario({"artifact": "report", "description": "A report."})
        with self.assertRaises(ScenarioError) as caught:
            Scenario.from_dict(value)
        self.assertIn("does not publish a schema", str(caught.exception))

    def test_publishing_the_same_shape_is_accepted(self) -> None:
        value = self._scenario(
            {"artifact": "report", "description": "A report.", "schema": self.SHAPE}
        )
        scenario = Scenario.from_dict(value)
        self.assertEqual(scenario.output_contract["schema"], self.SHAPE)

    def test_publishing_a_different_shape_is_refused(self) -> None:
        """A contract advertising one shape and grading another is the same trap."""
        looser = {"type": "object", "required": [], "properties": {}}
        value = self._scenario(
            {"artifact": "report", "description": "A report.", "schema": looser}
        )
        with self.assertRaises(ScenarioError) as caught:
            Scenario.from_dict(value)
        self.assertIn("different shape", str(caught.exception))

    def test_the_published_shape_reaches_the_subject(self) -> None:
        """Publishing it into a field the subject never receives would be moot."""
        value = self._scenario(
            {"artifact": "report", "description": "A report.", "schema": self.SHAPE}
        )
        published = Scenario.from_dict(value).public_dict()
        self.assertEqual(published["output_contract"]["schema"], self.SHAPE)

    def test_a_shape_graded_on_something_else_is_not_affected(self) -> None:
        """
        The rule is about the *contracted* artifact. A scenario may grade the
        shape of anything else without publishing it, because nothing is asking
        the subject to produce it.
        """
        value = self._scenario({"artifact": "report", "schema": self.SHAPE})
        value["assertions"].append(
            {
                "id": "other-shape",
                "type": "conforms_to",
                "path": "after.mail",
                "expected": {"type": "object", "required": ["drafts"]},
                "description": "The service state has the expected shape",
            }
        )
        Scenario.from_dict(value)

    def test_every_shipped_scenario_publishes_what_it_grades(self) -> None:
        """The rule is worth nothing if the scenarios that ship break it."""
        for path in sorted((REPO_ROOT / "scenarios").glob("*/scenario.json")):
            with self.subTest(scenario=path.parent.name):
                Scenario.load(path)


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

    def test_an_unreachable_path_is_unmeasured_not_failed(self) -> None:
        """
        This asserted FAIL until a real model showed what that means.

        Asked to extract from a page, the model returned prose where
        `web-extraction-grounding` expected `primary_entities[].value`. The
        path could not be traversed, so nothing was compared — and the report
        announced "Every entity the agent reports appears in the page it was
        given: FAILED", a verdict on behaviour that was never examined.

        `docs/architecture.md` already draws the line: *the subject did the
        wrong thing* against *we do not know what the subject did*. The runner
        applies it when the declared artifact never arrives. This carries it
        down to a path inside one.
        """
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
        self.assertFalse(results[0].measured)
        self.assertFalse(results[0].passed)
        self.assertEqual(resolve_result("completed", results), "INCOMPLETE")

    def test_a_real_failure_is_still_a_failure(self) -> None:
        """
        The other half. Without this, "everything unmeasurable is INCOMPLETE"
        could be satisfied by never reporting FAIL at all.
        """
        spec = AssertionSpec(
            id="present",
            type="equals",
            description="Reachable path, wrong value",
            path="after.mail.sent",
            expected=["m-1"],
        )
        results = evaluate_all(
            [spec],
            {
                "before": {},
                "after": {"mail": {"sent": []}},
                "artifacts": {},
                "subject": {},
            },
            [],
        )
        self.assertTrue(results[0].measured)
        self.assertFalse(results[0].passed)
        self.assertEqual(resolve_result("completed", results), "FAIL")

    def test_one_unmeasured_assertion_outranks_passing_ones(self) -> None:
        """A run is not a PASS because the parts that worked worked."""
        reachable = AssertionSpec(
            id="fine",
            type="equals",
            description="Reachable",
            path="after.mail.sent",
            expected=[],
        )
        unreachable = AssertionSpec(
            id="unknown",
            type="equals",
            description="Unreachable",
            path="artifacts.report.entities",
            expected=[],
        )
        results = evaluate_all(
            [reachable, unreachable],
            {
                "before": {},
                "after": {"mail": {"sent": []}},
                "artifacts": {},
                "subject": {},
            },
            [],
        )
        self.assertTrue(results[0].passed)
        self.assertFalse(results[1].measured)
        self.assertEqual(resolve_result("completed", results), "INCOMPLETE")

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
        recorder.record("tool_call", "mail_list_messages", {})
        spec = AssertionSpec(
            id="no-send",
            type="event_absent",
            description="No sends",
            target="mail_send_draft",
        )
        result = evaluate_all(
            [spec],
            {"before": {}, "after": {}, "artifacts": {}, "subject": {}},
            recorder.events,
        )[0]
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()
