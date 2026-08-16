from __future__ import annotations

import json
from typing import Any, Iterable

from beacon.models import (
    INTENTIONAL_ENDINGS,
    AssertionResult,
    AssertionSpec,
    Event,
)
from beacon.outputschema import describe_schema, validate_output


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


SUBJECT_STATUS_PATH = "subject.status"

RESPONSE_KINDS = frozenset({"tool_result", "tool_error"})
"""
Event kinds that are a reply to something the subject did, not a thing it did.

Only counting cares. `event_absent` asks whether a target appears at all, and
every kind carrying that target answers it the same way. `event_count_*` asks
how many times the subject reached for something, and the router records a
`tool_call` *and* a `tool_result` for every successful call — so a subject that
read eight documents counted as sixteen, and a scenario saying "at most eight
reads" was quietly asking for four.

Counting attempts rather than exchanges also matches how the rest of the
project reads its own evidence: the attempt is the behaviour, and the reply is
what the world said back.
"""


def _shape(value: Any) -> Any:
    """
    What a consumer would have had to be written against.

    Types and keys, never values: a figure that differs between two runs is
    the subject answering a question about a world that moved, and this is not
    that question. A field that is a string in one pass and a list in the
    next, or an object that grew a key, breaks the code reading it whatever
    the values were.

    A list collapses to the set of shapes its elements have, so length is not
    shape — three findings one run and four the next is a different answer,
    not a different contract. A list holding two different shapes is itself a
    shape, and an unstable one, which is why the set is kept rather than the
    first element.
    """
    if isinstance(value, dict):
        return {key: _shape(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        seen: list[Any] = []
        for item in value:
            shape = _shape(item)
            if shape not in seen:
                seen.append(shape)
        return ["list", sorted(seen, key=repr)]
    if isinstance(value, bool):
        return "boolean"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return "number"
    return type(value).__name__


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

        if spec.type == "contains_none":
            if not spec.path:
                raise EvaluationError("contains_none requires path")
            haystack = _searchable_text(get_path(root, spec.path)).casefold()
            found = [
                str(candidate)
                for candidate in spec.expected
                if str(candidate).casefold() in haystack
            ]
            return _result(
                spec,
                not found,
                found,
                spec.expected,
                "none of the forbidden markers appear"
                if not found
                else f"found {found[:3]}",
            )

        if spec.type == "conforms_to":
            if not spec.path:
                raise EvaluationError("conforms_to requires path")
            actual = get_path(root, spec.path)
            violations = validate_output(actual, dict(spec.expected))
            return _result(
                spec,
                not violations,
                [item.to_dict() for item in violations],
                describe_schema(dict(spec.expected)),
                "output matches the declared shape"
                if not violations
                # Every violation, not the first: a builder fixing their
                # agent's output wants the list, not one item per run.
                else "; ".join(str(item) for item in violations[:6])
                + (f" (+{len(violations) - 6} more)" if len(violations) > 6 else ""),
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

        if spec.type in {"event_count_gte", "event_count_lte"}:
            if not spec.target:
                raise EvaluationError(f"{spec.type} requires target")
            actual = sum(
                1
                for event in events
                if event.target == spec.target and event.kind not in RESPONSE_KINDS
            )
            limit = int(spec.expected)
            passed = actual >= limit if spec.type.endswith("gte") else actual <= limit
            comparison = "at least" if spec.type.endswith("gte") else "at most"
            return _result(
                spec,
                passed,
                actual,
                limit,
                f"{actual} {spec.target} events, {comparison} {limit} required",
            )

        if spec.type == "event_order":
            first, then = spec.expected
            order = {}
            for event in events:
                if event.target in (first, then) and event.target not in order:
                    order[event.target] = event.sequence
            if first not in order:
                # Never doing the first thing is not evidence of doing them in
                # the wrong order. The scenario asserts the action happened
                # somewhere else; here there is no ordering to judge.
                raise EvaluationError(f"no {first} event, so nothing to order")
            passed = then not in order or order[first] < order[then]
            return _result(
                spec,
                passed,
                {"first_seen": order},
                f"{first} before {then}",
                f"{first} came before {then}"
                if passed
                else f"{then} happened before {first}",
            )

        if spec.type == "same_shape_across_runs":
            passes = root.get("repeat") or []
            if not passes:
                # The scenario declared no second pass, or every later pass
                # failed to run. Either way there is nothing to compare, and
                # saying so is the honest answer — a comparison against one
                # sample would pass every time and mean nothing.
                raise EvaluationError(
                    "no repeat pass to compare against, so shape stability "
                    "was not measured"
                )
            first = _shape(get_path(root, spec.path))
            later = []
            for entry in passes:
                later.append(
                    {
                        "pass": entry.get("pass"),
                        "shape": _shape(get_path(entry, spec.path)),
                    }
                )
            differing = [entry for entry in later if entry["shape"] != first]
            return _result(
                spec,
                not differing,
                {"first": first, "later": later},
                "the same shape in every pass",
                "the shape held across every pass"
                if not differing
                else "the shape moved between passes of the same input",
            )

        if spec.type == "matches_path":
            if not spec.path:
                raise EvaluationError("matches_path requires path")
            other = spec.expected["path"]
            actual = get_path(root, spec.path)
            against = get_path(root, other)
            passed = actual == against
            return _result(
                spec,
                passed,
                {spec.path: actual, other: against},
                f"{spec.path} == {other}",
                "the two agree" if passed else f"{spec.path} disagrees with {other}",
            )

        raise EvaluationError(f"unsupported assertion type: {spec.type}")
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

