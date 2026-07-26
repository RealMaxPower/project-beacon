from __future__ import annotations

import json
from typing import Any, Iterable

from beacon.models import AssertionResult, AssertionSpec, Event


class EvaluationError(ValueError):
    """Raised when an assertion cannot be evaluated."""


def _searchable_text(value: Any) -> str:
    """
    Render a value so a text search reads its content.

    A subject may answer with prose or with structured JSON, and both are
    legitimate. Python's `in` on a dict tests keys, so a structured briefing
    that cites every message id would fail a citation check that a prose one
    passes. Serialising first makes the assertion about what the subject said
    rather than how it chose to shape it.
    """
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _contains(actual: Any, expected: Any) -> bool:
    """
    Substring search for text, membership for everything else.

    Text comparison is case-insensitive: models routinely normalise
    identifiers when writing prose, and "M-001" is the same citation as
    "m-001".
    """
    if not isinstance(expected, str):
        if isinstance(actual, (list, tuple, set, dict)):
            return expected in actual
        raise EvaluationError("contains needs a container or a string")
    return expected.casefold() in _searchable_text(actual).casefold()


def get_path(root: Any, path: str) -> Any:
    current = root
    for segment in path.split("."):
        if isinstance(current, dict):
            if segment not in current:
                raise EvaluationError(f"path does not exist: {path}")
            current = current[segment]
        elif isinstance(current, list) and segment.isdigit():
            index = int(segment)
            try:
                current = current[index]
            except IndexError as exc:
                raise EvaluationError(f"list index is out of range: {path}") from exc
        else:
            raise EvaluationError(f"path cannot be traversed: {path}")
    return current


def _result(
    spec: AssertionSpec,
    passed: bool,
    actual: Any,
    expected: Any,
    message: str,
) -> AssertionResult:
    return AssertionResult(
        id=spec.id,
        description=spec.description,
        passed=passed,
        actual=actual,
        expected=expected,
        message=message,
    )


def evaluate_assertion(
    spec: AssertionSpec,
    root: dict[str, Any],
    events: Iterable[Event],
) -> AssertionResult:
    try:
        if spec.type == "equals":
            if not spec.path:
                raise EvaluationError("equals requires path")
            actual = get_path(root, spec.path)
            return _result(
                spec,
                actual == spec.expected,
                actual,
                spec.expected,
                "values match" if actual == spec.expected else "values differ",
            )

        if spec.type in {"count_gte", "count_lte"}:
            if not spec.path:
                raise EvaluationError(f"{spec.type} requires path")
            value = get_path(root, spec.path)
            if not hasattr(value, "__len__"):
                raise EvaluationError(f"value at {spec.path} has no length")
            actual = len(value)
            expected = int(spec.expected)
            passed = actual >= expected if spec.type == "count_gte" else actual <= expected
            operator = ">=" if spec.type == "count_gte" else "<="
            return _result(
                spec,
                passed,
                actual,
                expected,
                f"{actual} {operator} {expected}" if passed else f"{actual} is not {operator} {expected}",
            )

        if spec.type == "contains":
            if not spec.path:
                raise EvaluationError("contains requires path")
            actual = get_path(root, spec.path)
            try:
                passed = _contains(actual, spec.expected)
            except TypeError as exc:
                raise EvaluationError(
                    f"value at {spec.path} does not support contains"
                ) from exc
            return _result(
                spec,
                passed,
                actual,
                spec.expected,
                "expected value found" if passed else "expected value not found",
            )

        if spec.type == "unchanged":
            if not spec.path:
                raise EvaluationError("unchanged requires path")
            before = get_path(root["before"], spec.path)
            after = get_path(root["after"], spec.path)
            return _result(
                spec,
                before == after,
                after,
                before,
                "state is unchanged" if before == after else "state changed",
            )

        if spec.type in {"event_absent", "event_present"}:
            if not spec.target:
                raise EvaluationError(f"{spec.type} requires target")
            matches = [event.to_dict() for event in events if event.target == spec.target]
            passed = not matches if spec.type == "event_absent" else bool(matches)
            expected = "absent" if spec.type == "event_absent" else "present"
            return _result(
                spec,
                passed,
                matches,
                expected,
                f"event {expected}" if passed else f"event should be {expected}",
            )

        raise EvaluationError(f"unsupported assertion type: {spec.type}")
    except EvaluationError as exc:
        return _result(spec, False, None, spec.expected, str(exc))
    except (TypeError, ValueError, KeyError, AttributeError, IndexError) as exc:
        # A malformed spec should have been caught at load time. If one gets
        # this far it becomes one failed assertion, not a crash that takes the
        # whole run - and the evidence - down with it.
        return _result(
            spec,
            False,
            None,
            spec.expected,
            f"assertion could not be evaluated: {type(exc).__name__}: {exc}",
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
    results = tuple(assertions)
    if subject_status != "completed":
        return "INCOMPLETE"
    if not results:
        return "INCOMPLETE"
    return "PASS" if all(result.passed for result in results) else "FAIL"

