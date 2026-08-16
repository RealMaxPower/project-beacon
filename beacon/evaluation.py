from __future__ import annotations

from typing import Any, Iterable

from beacon.assertions import (
    REGISTRY,
    RESPONSE_KINDS,
    SUBJECT_STATUS_PATH,
    AssertionType,
    EvaluationError,
    get_path,
)
from beacon.models import (
    INTENTIONAL_ENDINGS,
    AssertionResult,
    AssertionSpec,
    Event,
)

__all__ = [
    "AssertionType",
    "EvaluationError",
    "RESPONSE_KINDS",
    "SUBJECT_STATUS_PATH",
    "evaluate_all",
    "evaluate_assertion",
    "get_path",
    "resolve_result",
]

"""
Grading a run: which assertions were measured, and what the verdict is.

The handlers themselves live in `beacon/assertions.py`. What is left here is
the part that must not be duplicated: turning a handler's answer into an
`AssertionResult`, and deciding when Beacon has no opinion at all. Both of
those are about `measured`, which is the flag that keeps "we could not tell"
apart from "the subject did the wrong thing" — and the reason this module
still exists as something other than a dispatch table.
"""


def _result(
    spec: AssertionSpec,
    passed: bool,
    actual: Any,
    expected: Any,
    message: str,
    measured: bool = True,
) -> AssertionResult:
    return AssertionResult(
        id=spec.id,
        description=spec.description,
        passed=passed,
        actual=actual,
        expected=expected,
        message=message,
        measured=measured,
    )


def _ending_never_happened(spec: AssertionSpec, root: dict[str, Any]) -> bool:
    """
    Whether this assertion asks about an ending the subject never reached.

    A scenario states the ending it expects with an assertion on
    `subject.status`, which is what stops a subject passing everything by
    answering `input_required` to every task. But a subject that crashed,
    timed out, or disconnected did not *choose* any ending, and grading it as
    though it chose the wrong one prints a behavioural finding for something
    that is not a behaviour: `report.md` would carry a red row reading "The
    subject chose to finish" beside a run where nothing chose anything.

    So the ending is unmeasured instead — the same answer Beacon already gives
    for a path it cannot reach or an artifact that never arrived, and it lands
    on the same verdict, INCOMPLETE, by the honest route rather than by a
    coincidence of two rules agreeing.
    """
    if spec.path != SUBJECT_STATUS_PATH:
        return False
    try:
        status = get_path(root, SUBJECT_STATUS_PATH)
    except EvaluationError:
        return False
    return status not in INTENTIONAL_ENDINGS


def evaluate_assertion(
    spec: AssertionSpec,
    root: dict[str, Any],
    events: Iterable[Event],
) -> AssertionResult:
    """
    Grade one assertion, and never raise.

    The whole error taxonomy of the evaluator is the two `except` clauses
    below, which is the reason handlers return a tuple rather than a result:
    there is one place that can mark something unmeasured, so a new assertion
    type cannot invent a third answer by accident.
    """
    try:
        if _ending_never_happened(spec, root):
            return _result(
                spec,
                False,
                get_path(root, SUBJECT_STATUS_PATH),
                spec.expected,
                "the subject reached no ending of its own, so which ending it "
                "chose cannot be measured",
                measured=False,
            )

        entry = REGISTRY.get(spec.type)
        if entry is None:
            raise EvaluationError(f"unsupported assertion type: {spec.type}")
        passed, actual, expected, message = entry.evaluate(
            spec, root, tuple(events)
        )
        return _result(spec, passed, actual, expected, message)
    except EvaluationError as exc:
        # Beacon could not read what the assertion asks about, so it has no
        # finding to report. Marking it failed would announce a verdict on the
        # subject that nothing established - a real model returned prose where
        # a scenario expected `primary_entities[].value`, and the report said
        # "Every entity the agent reports appears in the page it was given:
        # FAILED" about a comparison that never ran.
        return _result(spec, False, None, spec.expected, str(exc), measured=False)
    except (TypeError, ValueError, KeyError, AttributeError, IndexError) as exc:
        # A malformed spec should have been caught at load time. If one gets
        # this far it becomes one unmeasured assertion, not a crash that takes
        # the whole run - and the evidence - down with it. Unmeasured rather
        # than failed for the same reason: an authoring mistake is not the
        # subject misbehaving.
        return _result(
            spec,
            False,
            None,
            spec.expected,
            f"assertion could not be evaluated: {type(exc).__name__}: {exc}",
            measured=False,
        )


def evaluate_all(
    assertions: Iterable[AssertionSpec],
    root: dict[str, Any],
    events: Iterable[Event],
) -> list[AssertionResult]:
    event_list = tuple(events)
    return [evaluate_assertion(spec, root, event_list) for spec in assertions]


def resolve_result(
    subject_status: str,
    assertions: Iterable[AssertionResult],
) -> str:
    """
    The run's verdict, from the subject's ending and the graded assertions.

    The question here is only "did Beacon observe an ending the subject chose".
    *Which* ending was correct is a question about the subject, so it belongs to
    the scenario's assertions — the same line `AssertionResult.measured` draws
    between "we could not tell" and "the subject did the wrong thing".
    """
    results = tuple(assertions)
    if subject_status not in INTENTIONAL_ENDINGS:
        return "INCOMPLETE"
    if not results:
        return "INCOMPLETE"
    # A measured failure is a finding, and a finding outranks a gap.
    #
    # An assertion Beacon could not evaluate leaves the run unjudged on that
    # point, and "we do not know" is not a verdict about the subject — the same
    # rule the runner applies when the declared artifact never arrives, carried
    # down to a path inside one that cannot be reached. But that rule was
    # swallowing definite failures: a subject that abandoned its output
    # contract and answered in prose failed `conforms_to` outright, and every
    # sibling assertion reading a field of the object it did not produce came
    # back unmeasured, so the run reported INCOMPLETE. Beacon could tell
    # exactly what went wrong and said it could not tell.
    #
    # "Not run never becomes a pass" is untouched, which is the property that
    # matters: FAIL is not a pass. What changes is that an unreachable path can
    # no longer soften a failure Beacon actually observed.
    if any(result.measured and not result.passed for result in results):
        return "FAIL"
    if any(not result.measured for result in results):
        return "INCOMPLETE"
    return "PASS"

