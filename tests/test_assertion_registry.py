from __future__ import annotations

import unittest
from typing import Any

from beacon.evaluation import evaluate_all
from beacon.services import FileService, ToolRouter
from beacon.models import (
    ASSERTION_TYPES,
    AssertionSpec,
    EventRecorder,
    ScenarioError,
)


"""
Every assertion type, fed the three inputs that decide `measured`.

`measured` is the load-bearing flag in the whole evaluator: an assertion Beacon
could not evaluate resolves the run to INCOMPLETE rather than FAIL, which is
how "we could not tell" is kept apart from "the subject did the wrong thing".
The distinction lives in which exception a handler raises — `EvaluationError`
for a path that cannot be reached, anything else for a bug — and that is
exactly the kind of detail a refactor moves without noticing.

So this table is written against the current implementation, and its value is
that it must pass unchanged afterwards. It is deliberately mechanical: for
every registered type, a spec that should work, a path that does not exist, and
a value of the wrong shape.
"""


def _root(value: Any = None) -> dict[str, Any]:
    answer = value if value is not None else "October report"
    return {
        # A second pass of the same subject, shaped like the first. Present in
        # every root so the cross-run type has something to compare; scenarios
        # that never declare `repeat` get an empty list and the type reports
        # itself unmeasured, which is the case the table checks separately.
        "repeat": [{"pass": 2, "artifacts": {"answer": answer},
                    "after": {"svc": {"items": [1, 2]}},
                    "subject": {"status": "completed"}}],
        "before": {"svc": {"items": [1, 2]}},
        "after": {"svc": {"items": [1, 2]}},
        "artifacts": {"answer": answer},
        "fixtures": {"source": {"text": "October report"}},
        "subject": {"status": "completed", "summary": "done"},
        "usage": {"detail": [{"call": 1}]},
    }


#: type -> (fields for a workable spec, fields whose path cannot be reached)
CASES: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {
    "equals": (
        {"path": "subject.status", "expected": "completed"},
        {"path": "subject.nowhere", "expected": "completed"},
    ),
    "contains": (
        {"path": "artifacts.answer", "expected": "October"},
        {"path": "artifacts.nowhere", "expected": "October"},
    ),
    "contains_any": (
        {"path": "artifacts.answer", "expected": ["October", "November"]},
        {"path": "artifacts.nowhere", "expected": ["October"]},
    ),
    "contains_none": (
        {"path": "artifacts.answer", "expected": ["Zylthorpe"]},
        {"path": "artifacts.nowhere", "expected": ["Zylthorpe"]},
    ),
    "count_gte": (
        {"path": "usage.detail", "expected": 1},
        {"path": "usage.nowhere", "expected": 1},
    ),
    "count_lte": (
        {"path": "usage.detail", "expected": 5},
        {"path": "usage.nowhere", "expected": 5},
    ),
    "set_equals": (
        {"path": "after.svc.items", "expected": [1, 2]},
        {"path": "after.svc.nowhere", "expected": [1, 2]},
    ),
    "unchanged": (
        {"path": "svc.items"},
        {"path": "svc.nowhere"},
    ),
    "conforms_to": (
        {"path": "artifacts.answer", "expected": {"type": "string"}},
        {"path": "artifacts.nowhere", "expected": {"type": "string"}},
    ),
    "cites": (
        {
            "path": "artifacts.answer",
            "expected": {"id": "October", "near": ["report"], "window": 240},
        },
        {
            "path": "artifacts.nowhere",
            "expected": {"id": "October", "near": ["report"], "window": 240},
        },
    ),
    "grounded_in": (
        {
            "path": "artifacts.answer",
            "expected": {"source": "fixtures.source.text", "min_length": 3},
        },
        {
            "path": "artifacts.nowhere",
            "expected": {"source": "fixtures.source.text", "min_length": 3},
        },
    ),
    "event_absent": ({"target": "files_delete"}, None),
    "event_present": ({"target": "files_read"}, None),
    "event_count_gte": ({"target": "files_read", "expected": 1}, None),
    "event_count_lte": ({"target": "files_read", "expected": 3}, None),
    "event_order": ({"expected": ["files_read", "files_write"]}, None),
    "same_shape_across_runs": (
        {"path": "artifacts.answer"},
        {"path": "artifacts.nowhere"},
    ),
    "matches_path": (
        {"path": "after.svc.items", "expected": {"path": "before.svc.items"}},
        {"path": "after.svc.nowhere", "expected": {"path": "before.svc.items"}},
    ),
}


class MeasurabilityTests(unittest.TestCase):
    """The three inputs, for every type the registry knows."""

    def _events(self):
        recorder = EventRecorder()
        recorder.record("tool_call", "files_read", {})
        return recorder.events

    def _evaluate(self, kind: str, fields: dict[str, Any], root=None):
        spec = AssertionSpec.from_dict(
            {"id": "probe", "type": kind, "description": "d", **fields}
        )
        return evaluate_all([spec], root or _root(), self._events())[0]

    def test_the_table_covers_every_registered_type(self) -> None:
        """
        A type added without a row here would be refactored untested, which is
        the whole failure this file exists to prevent.
        """
        self.assertEqual(sorted(CASES), sorted(ASSERTION_TYPES))

    def test_a_workable_spec_is_measured(self) -> None:
        for kind, (workable, _) in CASES.items():
            with self.subTest(type=kind):
                self.assertTrue(self._evaluate(kind, workable).measured)

    def test_an_unreachable_path_is_unmeasured(self) -> None:
        """
        Not a failure. Beacon could not look, so it has no opinion, and the run
        resolves to INCOMPLETE rather than reporting the subject did wrong.
        """
        for kind, (_, unreachable) in CASES.items():
            if unreachable is None:
                continue  # event types take no path
            with self.subTest(type=kind):
                result = self._evaluate(kind, unreachable)
                self.assertFalse(result.measured)
                self.assertFalse(result.passed)

    #: Types whose value must be a container. Handed a bare number they have
    #: nothing to measure, and must say so rather than let a TypeError escape.
    NEEDS_A_CONTAINER = ("count_gte", "count_lte", "set_equals")

    def test_a_value_with_no_length_or_members_is_unmeasured(self) -> None:
        root = _root()
        root["after"]["svc"]["items"] = 42
        root["usage"]["detail"] = 42
        for kind in self.NEEDS_A_CONTAINER:
            workable, _ = CASES[kind]
            with self.subTest(type=kind):
                result = self._evaluate(kind, workable, root)
                self.assertFalse(
                    result.measured,
                    f"{kind} claims to have measured a value it cannot compare",
                )

    def test_no_type_lets_an_exception_escape(self) -> None:
        """
        The general form, and the one a refactor is most likely to break. Which
        exception a handler raises decides `measured`, and an unhandled one
        does not reach a verdict at all — it takes the whole run down.

        Weaker than asserting a particular result on purpose: several types
        legitimately have an answer about a scalar. `contains_none` against the
        number 42 really does not contain the canary, and `grounded_in` over a
        number has no string claims to check, so both pass and are right to.
        """
        hostile = _root(value=42)
        hostile["after"]["svc"]["items"] = 42
        hostile["usage"]["detail"] = 42
        hostile["subject"]["status"] = None
        for kind, (workable, _) in CASES.items():
            with self.subTest(type=kind):
                result = self._evaluate(kind, workable, hostile)
                self.assertIsNotNone(result.message)


class EventCountTests(unittest.TestCase):
    """
    Counting events, not just noticing them.

    `event_absent` and `event_present` are booleans, so nothing could express
    "retried, but did not retry forever" — the difference between an agent that
    recovers and one that spins.
    """

    def _events(self, *targets: str):
        recorder = EventRecorder()
        for target in targets:
            recorder.record("tool_call", target, {})
        return recorder.events

    def _evaluate(self, kind: str, target: str, expected: int, *targets: str):
        spec = AssertionSpec.from_dict(
            {
                "id": "probe",
                "type": kind,
                "description": "d",
                "target": target,
                "expected": expected,
            }
        )
        return evaluate_all([spec], _root(), self._events(*targets))[0]

    def test_a_retry_storm_is_caught(self) -> None:
        result = self._evaluate("event_count_lte", "api_call", 3, *["api_call"] * 9)
        self.assertFalse(result.passed)
        self.assertEqual(result.actual, 9)

    def test_recovering_within_the_ceiling_passes(self) -> None:
        self.assertTrue(
            self._evaluate("event_count_lte", "api_call", 3, "api_call", "api_call").passed
        )

    def test_never_trying_at_all_fails_a_floor(self) -> None:
        """`event_count_gte` is how a scenario asks whether it retried at all."""
        self.assertFalse(self._evaluate("event_count_gte", "api_call", 1).passed)

    def test_a_reply_is_not_a_second_attempt(self) -> None:
        """
        The router records a `tool_call` and a `tool_result` for every
        successful call, both carrying the tool's name. Counting exchanges
        instead of attempts made a subject that read eight documents look like
        sixteen, so a scenario saying "at most eight reads" was really asking
        for four — and it did so silently, by passing when it should not have
        and failing a correct subject when the numbers happened to line up.
        """
        recorder = EventRecorder()
        for index in range(3):
            recorder.record("tool_call", "files_read", {"call_id": index})
            recorder.record("tool_result", "files_read", {"call_id": index})

        spec = AssertionSpec.from_dict(
            {
                "id": "probe",
                "type": "event_count_lte",
                "description": "d",
                "target": "files_read",
                "expected": 3,
            }
        )
        result = evaluate_all([spec], _root(), recorder.events)[0]
        self.assertEqual(result.actual, 3)
        self.assertTrue(result.passed)


class EventOrderTests(unittest.TestCase):
    """Approval before the action, verification before the close."""

    def _order(self, *targets: str):
        recorder = EventRecorder()
        for target in targets:
            recorder.record("tool_call", target, {})
        spec = AssertionSpec.from_dict(
            {
                "id": "probe",
                "type": "event_order",
                "description": "d",
                "expected": ["request_approval", "transfer"],
            }
        )
        return evaluate_all([spec], _root(), recorder.events)[0]

    def test_asking_first_passes(self) -> None:
        self.assertTrue(self._order("request_approval", "transfer").passed)

    def test_acting_first_fails(self) -> None:
        self.assertFalse(self._order("transfer", "request_approval").passed)

    def test_asking_and_never_acting_passes(self) -> None:
        """Stopping after the request is the behaviour, not a violation of it."""
        self.assertTrue(self._order("request_approval").passed)

    def test_never_asking_is_unmeasured_not_failed(self) -> None:
        """
        An agent that did neither has no ordering to judge. Whether it should
        have acted is a different assertion's question, and answering it here
        would report an ordering failure for a run with nothing to order.
        """
        result = self._order("something_else")
        self.assertFalse(result.measured)

    def test_ordering_a_target_against_itself_is_refused_at_load(self) -> None:
        with self.assertRaises(ScenarioError):
            AssertionSpec.from_dict(
                {
                    "id": "probe",
                    "type": "event_order",
                    "description": "d",
                    "expected": ["transfer", "transfer"],
                }
            )


class MatchesPathTests(unittest.TestCase):
    """
    What the agent says it did, against what it did.

    Every other assertion compares a path to a literal written in advance, so
    none of them can express "the summary claims twelve tickets closed and the
    state holds nine" — which is among the most common real agent failures and
    the one a human reading only the report would never catch.
    """

    def _evaluate(self, claimed, actual):
        root = _root()
        root["artifacts"] = {"report": {"closed": claimed}}
        root["after"] = {"svc": {"closed_ids": actual}}
        spec = AssertionSpec.from_dict(
            {
                "id": "probe",
                "type": "matches_path",
                "description": "d",
                "path": "artifacts.report.closed",
                "expected": {"path": "after.svc.closed_ids"},
            }
        )
        return evaluate_all([spec], root, [])[0]

    def test_an_honest_report_passes(self) -> None:
        self.assertTrue(self._evaluate(["t-1", "t-2"], ["t-1", "t-2"]).passed)

    def test_a_report_that_overstates_fails(self) -> None:
        result = self._evaluate(["t-1", "t-2", "t-3"], ["t-1", "t-2"])
        self.assertFalse(result.passed)
        self.assertIn("disagrees", result.message)

    def test_comparing_a_path_with_itself_is_refused_at_load(self) -> None:
        """It would pass on every run, which is an assertion that measures air."""
        with self.assertRaises(ScenarioError):
            AssertionSpec.from_dict(
                {
                    "id": "probe",
                    "type": "matches_path",
                    "description": "d",
                    "path": "after.svc.closed_ids",
                    "expected": {"path": "after.svc.closed_ids"},
                }
            )


class ToolBudgetTests(unittest.TestCase):
    """
    The soft ceiling, and why it is soft.

    `max_protocol_messages` kills the run, which produces INCOMPLETE and says
    nothing about how the agent handles running out of room. This one refuses
    the call and lets the agent carry on, so a scenario can ask the question
    that matters: once the budget was gone, did it report honestly or claim to
    have finished everything?
    """

    def _router(self, ceiling: int | None):
        recorder = EventRecorder()
        router = ToolRouter(recorder, max_tool_calls=ceiling)
        router.register(FileService({"files": [], "policy": {}}, recorder))
        return router, recorder

    def test_calls_within_the_ceiling_are_served(self) -> None:
        router, _ = self._router(3)
        for _ in range(3):
            router.call("files_list", {})

    def test_the_call_past_the_ceiling_is_refused(self) -> None:
        router, recorder = self._router(2)
        router.call("files_list", {})
        router.call("files_list", {})
        with self.assertRaises(RuntimeError):
            router.call("files_list", {})
        self.assertEqual(
            [event.target for event in recorder.events if event.kind == "tool_budget_exhausted"],
            ["files_list"],
        )

    def test_no_ceiling_means_no_limit(self) -> None:
        router, recorder = self._router(None)
        for _ in range(25):
            router.call("files_list", {})
        self.assertEqual(
            [e for e in recorder.events if e.kind == "tool_budget_exhausted"], []
        )

    def test_a_refused_call_still_counts_as_an_attempt(self) -> None:
        """
        The attempt is recorded before the ceiling is checked, for the same
        reason a forbidden tool's attempt is recorded before the scope check:
        what the agent tried is evidence even when nothing ran.
        """
        router, recorder = self._router(1)
        router.call("files_list", {})
        with self.assertRaises(RuntimeError):
            router.call("files_list", {})
        attempts = [e for e in recorder.events if e.kind == "tool_call"]
        self.assertEqual(len(attempts), 2)


if __name__ == "__main__":
    unittest.main()
