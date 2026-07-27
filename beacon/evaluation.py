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


def _flatten_claims(value: Any) -> list[str]:
    """
    Reduce whatever an agent returned to the list of strings it asserted.

    An extraction result is nested — entities holding values, values holding
    lists of tags — and every leaf string is a claim about the source that can
    be checked against it. Numbers and booleans are excluded: they coincide
    with source text far too often to mean anything.
    """
    claims: list[str] = []
    if isinstance(value, str):
        claims.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            claims.extend(_flatten_claims(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            claims.extend(_flatten_claims(item))
    return [claim.strip() for claim in claims if claim and claim.strip()]


def _cited_near(
    text: str,
    reference: str,
    near: list[str],
    window: int,
) -> str | None:
    """
    Find a corroborating token within `window` characters of a reference.

    A bare substring check cannot tell a citation from a name-drop: "unable to
    review m-001" satisfies `contains "m-001"` exactly as well as a real
    briefing does. Requiring the identifier to appear beside something only
    that message contains raises the bar without reaching for an LLM judge, so
    the result stays deterministic and reproducible.

    Returns the token that corroborated the citation, for the evidence record.
    """
    start = 0
    while True:
        position = text.find(reference, start)
        if position < 0:
            return None
        left = max(0, position - window)
        right = position + len(reference) + window
        neighbourhood = text[left:right]
        for token in near:
            if token in neighbourhood:
                return token
        start = position + 1


def _hashable(value: Any) -> Any:
    """Make a JSON value usable in a set, preserving equality semantics."""
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return value


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
    """
    Resolve a dotted path, where `*` projects a field across a list.

    `after.mail.drafts.*.in_reply_to` collects `in_reply_to` from every draft,
    which is what lets a scenario assert *which* messages a subject replied to
    rather than only how many replies it wrote.
    """
    current = root
    segments = path.split(".")
    for index, segment in enumerate(segments):
        if segment == "*":
            if not isinstance(current, list):
                raise EvaluationError(
                    f"'*' needs a list at this point in the path: {path}"
                )
            remainder = ".".join(segments[index + 1 :])
            if not remainder:
                return list(current)
            return [get_path(item, remainder) for item in current]
        if isinstance(current, dict):
            if segment not in current:
                raise EvaluationError(f"path does not exist: {path}")
            current = current[segment]
        elif isinstance(current, list) and segment.isdigit():
            try:
                current = current[int(segment)]
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

        if spec.type == "contains_any":
            if not spec.path:
                raise EvaluationError("contains_any requires path")
            haystack = _searchable_text(get_path(root, spec.path)).casefold()
            found = [
                str(candidate)
                for candidate in spec.expected
                if str(candidate).casefold() in haystack
            ]
            return _result(
                spec,
                bool(found),
                found,
                spec.expected,
                f"found {found[:3]}" if found else "none of the expected values appear",
            )

        if spec.type == "grounded_in":
            if not spec.path:
                raise EvaluationError("grounded_in requires path")
            claims = _flatten_claims(get_path(root, spec.path))
            source = _searchable_text(
                get_path(root, str(spec.expected["source"]))
            ).casefold()
            minimum = int(spec.expected.get("min_length", 3))
            ignored = {str(item).casefold() for item in spec.expected.get("ignore", [])}
            ungrounded = [
                claim
                for claim in claims
                if len(claim) >= minimum
                and claim.casefold() not in ignored
                and claim.casefold() not in source
            ]
            passed = not ungrounded
            return _result(
                spec,
                passed,
                ungrounded or claims,
                {"source": spec.expected["source"], "checked": len(claims)},
                f"all {len(claims)} claim(s) appear in the source"
                if passed
                else (
                    f"{len(ungrounded)} of {len(claims)} claim(s) do not appear in "
                    f"the source: {ungrounded[:5]}"
                ),
            )

        if spec.type == "cites":
            if not spec.path:
                raise EvaluationError("cites requires path")
            text = _searchable_text(get_path(root, spec.path)).casefold()
            reference = str(spec.expected["id"]).casefold()
            near = [str(token).casefold() for token in spec.expected["near"]]
            window = int(spec.expected.get("window", 240))
            found = _cited_near(text, reference, near, window)
            return _result(
                spec,
                bool(found),
                found or f"{spec.expected['id']} not corroborated",
                spec.expected,
                f"cited alongside '{found}'"
                if found
                else (
                    f"{spec.expected['id']} does not appear within {window} "
                    f"characters of any of {spec.expected['near']}"
                ),
            )

        if spec.type == "set_equals":
            if not spec.path:
                raise EvaluationError("set_equals requires path")
            value = get_path(root, spec.path)
            if not isinstance(value, list):
                raise EvaluationError(f"set_equals needs a list at {spec.path}")
            if not isinstance(spec.expected, list):
                raise EvaluationError("set_equals expects a list")
            actual_set = set(map(_hashable, value))
            expected_set = set(map(_hashable, spec.expected))
            passed = actual_set == expected_set
            return _result(
                spec,
                passed,
                sorted(value, key=repr),
                sorted(spec.expected, key=repr),
                "sets match"
                if passed
                else f"missing {sorted(expected_set - actual_set, key=repr)}, "
                f"unexpected {sorted(actual_set - expected_set, key=repr)}",
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

