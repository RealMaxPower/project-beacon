from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from beacon.outputschema import SchemaError, validate_schema


class ScenarioError(ValueError):
    """Raised when a scenario is invalid."""


SCENARIO_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")

SCENARIO_KEYS = frozenset(
    {
        "schema_version",
        "id",
        "name",
        "description",
        "goal",
        "fixtures",
        "assertions",
        "tools",
        "output_contract",
        "limits",
        "metadata",
    }
)

ASSERTION_KEYS = frozenset({"id", "type", "description", "path", "expected", "target"})

ASSERTION_TYPES: dict[str, dict[str, Any]] = {
    "equals": {"requires": ("path", "expected")},
    "count_gte": {"requires": ("path", "expected"), "numeric_expected": True},
    "count_lte": {"requires": ("path", "expected"), "numeric_expected": True},
    "contains": {"requires": ("path", "expected")},
    "contains_any": {"requires": ("path", "expected"), "list_expected": True},
    "contains_none": {"requires": ("path", "expected"), "list_expected": True},
    "conforms_to": {"requires": ("path", "expected"), "schema_expected": True},
    "grounded_in": {"requires": ("path", "expected"), "grounding_expected": True},
    "cites": {"requires": ("path", "expected"), "citation_expected": True},
    "set_equals": {"requires": ("path", "expected")},
    "unchanged": {"requires": ("path",)},
    "event_absent": {"requires": ("target",)},
    "event_present": {"requires": ("target",)},
}
"""
Every assertion type and what it needs to be evaluable.

Checked when the scenario loads rather than when it runs. An assertion that
cannot be evaluated is an authoring mistake, and discovering it mid-run means
discovering it after the subject has already done the work - reported either as
a failure the subject did not earn, or as a crash that discards the evidence
for a run someone has already paid for.
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


MAX_STRUCTURE_DEPTH = 64
DEPTH_MARKER = f"[truncated by Beacon: nested deeper than {MAX_STRUCTURE_DEPTH} levels]"


def bound_depth(value: Any, limit: int = MAX_STRUCTURE_DEPTH) -> tuple[Any, bool]:
    """
    A copy of `value` with anything nested past `limit` replaced by a marker,
    and whether that happened.

    Everything the subject sends is walked again later by `dataclasses.asdict`
    and by the pure-Python JSON encoder, both of which spend more stack per
    level than the C decoder that accepted it. So a structure Beacon can parse
    is not necessarily one it can write, and a subject that nests a few hundred
    deep can raise `RecursionError` out of the evidence write — after it has
    already acted, taking the record of what it did with it.

    Truncating rather than rejecting keeps the run: the artifact is still
    recorded, the marker says what was dropped, and the verdict still lands.
    """
    if limit <= 0:
        return DEPTH_MARKER, True
    if isinstance(value, dict):
        truncated = False
        bounded = {}
        for key, item in value.items():
            bounded[key], hit = bound_depth(item, limit - 1)
            truncated = truncated or hit
        return bounded, truncated
    if isinstance(value, (list, tuple)):
        truncated = False
        bounded = []
        for item in value:
            item_value, hit = bound_depth(item, limit - 1)
            bounded.append(item_value)
            truncated = truncated or hit
        return bounded, truncated
    return value, False


@dataclass(frozen=True)
class AssertionSpec:
    id: str
    type: str
    description: str
    path: str | None = None
    expected: Any = None
    target: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AssertionSpec":
        for required in ("id", "type", "description"):
            if not value.get(required):
                raise ScenarioError(f"assertion is missing required field: {required}")
        identifier = str(value["id"])
        unknown = sorted(set(value) - ASSERTION_KEYS)
        if unknown:
            raise ScenarioError(
                f"assertion '{identifier}' has unknown fields: {', '.join(unknown)}"
            )
        kind = str(value["type"])
        rule = ASSERTION_TYPES.get(kind)
        if rule is None:
            supported = ", ".join(sorted(ASSERTION_TYPES))
            raise ScenarioError(
                f"assertion '{identifier}' has unsupported type '{kind}'. "
                f"Supported types: {supported}"
            )
        for name in rule["requires"]:
            if name not in value:
                raise ScenarioError(
                    f"{kind} assertion '{identifier}' requires '{name}'"
                )
        for name in ("path", "target"):
            if name in rule["requires"] and not str(value[name] or "").strip():
                raise ScenarioError(
                    f"{kind} assertion '{identifier}' needs a non-empty '{name}'"
                )
        # A field this type does not read is worse than a missing one: it is
        # silently ignored, so the author believes they constrained something
        # they did not, and the resulting verdict looks like the agent's
        # failure rather than the scenario's.
        ignored = sorted(
            name
            for name in ("path", "expected", "target")
            if name in value and name not in rule["requires"]
        )
        if ignored:
            raise ScenarioError(
                f"{kind} assertion '{identifier}' does not use "
                f"{', '.join(repr(name) for name in ignored)}; the field would "
                f"be ignored. {kind} reads {', '.join(rule['requires'])}."
            )
        if rule.get("citation_expected"):
            expected = value["expected"]
            if not isinstance(expected, dict):
                raise ScenarioError(
                    f"cites assertion '{identifier}' needs an object 'expected' "
                    f"with 'id' and 'near'"
                )
            for key in ("id", "near"):
                if not expected.get(key):
                    raise ScenarioError(
                        f"cites assertion '{identifier}' needs a non-empty "
                        f"'expected.{key}'"
                    )
            if not isinstance(expected["near"], list):
                raise ScenarioError(
                    f"cites assertion '{identifier}' needs 'expected.near' "
                    f"to be an array of corroborating tokens"
                )
            window = expected.get("window", 240)
            if isinstance(window, bool) or not isinstance(window, int) or window < 1:
                raise ScenarioError(
                    f"cites assertion '{identifier}' needs a positive integer "
                    f"'expected.window'"
                )
            # The window is searched around the reference and includes it, so a
            # token that is part of the reference is found every time the
            # reference appears. That turns the assertion back into the bare
            # substring check it exists to replace: naming the document
            # satisfies it, which is precisely a name-drop.
            reference = str(expected["id"]).casefold()
            self_satisfying = sorted(
                str(token)
                for token in expected["near"]
                if str(token).casefold() in reference
            )
            if self_satisfying:
                raise ScenarioError(
                    f"cites assertion '{identifier}' has corroborating "
                    f"token(s) {', '.join(repr(t) for t in self_satisfying)} "
                    f"inside its own reference {expected['id']!r}. They would "
                    f"be found whenever the reference is, so the assertion "
                    f"would pass on a name-drop. Use a token that appears only "
                    f"in the referenced content."
                )
        if rule.get("list_expected"):
            expected = value["expected"]
            if not isinstance(expected, list) or not expected:
                raise ScenarioError(
                    f"{kind} assertion '{identifier}' needs a non-empty array "
                    f"'expected'"
                )
        if rule.get("schema_expected"):
            try:
                validate_schema(value["expected"], path=f"assertion '{identifier}'")
            except SchemaError as error:
                raise ScenarioError(str(error)) from error
        if rule.get("grounding_expected"):
            expected = value["expected"]
            if not isinstance(expected, dict) or not expected.get("source"):
                raise ScenarioError(
                    f"grounded_in assertion '{identifier}' needs an object "
                    f"'expected' with a 'source' path to check claims against"
                )
            for key, default in (("min_length", 3),):
                given = expected.get(key, default)
                if isinstance(given, bool) or not isinstance(given, int) or given < 1:
                    raise ScenarioError(
                        f"grounded_in assertion '{identifier}' needs a positive "
                        f"integer 'expected.{key}'"
                    )
            if not isinstance(expected.get("ignore", []), list):
                raise ScenarioError(
                    f"grounded_in assertion '{identifier}' needs "
                    f"'expected.ignore' to be an array"
                )
        if rule.get("numeric_expected"):
            expected = value["expected"]
            if isinstance(expected, bool) or not isinstance(expected, (int, float)):
                raise ScenarioError(
                    f"{kind} assertion '{identifier}' needs a numeric 'expected', "
                    f"got {type(expected).__name__}"
                )
        return cls(
            id=str(value["id"]),
            type=str(value["type"]),
            description=str(value["description"]),
            path=value.get("path"),
            expected=value.get("expected"),
            target=value.get("target"),
        )


def _check_shape_is_published(
    assertions: tuple["AssertionSpec", ...],
    output_contract: dict[str, Any],
) -> None:
    """
    Refuse a scenario that grades a shape it never showed the subject.

    `output_contract` is the only part of a scenario the subject is told, so a
    `conforms_to` on the contracted artifact is a requirement the subject can
    only meet by guessing unless the same schema is published there. Both
    web-extraction scenarios did exactly that: they demanded `url`,
    `page_type`, `primary_entities`, `tables`, `actions` and `metadata` while
    the contract said only "Structured extraction of the page at the URL in
    the goal". That shape was one hosted agent's native output format, so the
    scenarios could grade that agent and nothing else — a real model returned
    prose and was marked down for a schema it was never shown.

    The schemas must be equal, not merely present. A contract that publishes
    one shape and grades a stricter one is the same trap wearing a disguise.
    """
    artifact = output_contract.get("artifact")
    if not artifact:
        return
    target = f"artifacts.{artifact}"
    published = output_contract.get("schema")
    for spec in assertions:
        if spec.type != "conforms_to" or spec.path != target:
            continue
        if published is None:
            raise ScenarioError(
                f"assertion {spec.id!r} grades the shape of {artifact!r}, but "
                f"output_contract does not publish a schema. The subject is "
                f"never shown the assertions, so it would have to guess the "
                f"shape. Add the same schema under output_contract.schema."
            )
        if published != spec.expected:
            raise ScenarioError(
                f"assertion {spec.id!r} grades a different shape from the one "
                f"output_contract.schema publishes to the subject. A contract "
                f"that advertises one shape and grades another is a hidden "
                f"requirement."
            )


@dataclass(frozen=True)
class Scenario:
    schema_version: str
    id: str
    name: str
    description: str
    goal: str
    fixtures: dict[str, Any]
    assertions: tuple[AssertionSpec, ...]
    tools: tuple[str, ...] | None = None
    output_contract: dict[str, Any] = field(default_factory=dict)
    limits: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def required_artifact(self) -> str | None:
        """The artifact name the subject must produce, if the scenario says."""
        name = self.output_contract.get("artifact")
        return str(name) if name else None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Scenario":
        required = (
            "schema_version",
            "id",
            "name",
            "description",
            "goal",
            "fixtures",
            "assertions",
        )
        for key in required:
            if key not in value:
                raise ScenarioError(f"scenario is missing required field: {key}")
        if value["schema_version"] != "0.1":
            raise ScenarioError(
                f"unsupported scenario schema_version: {value['schema_version']}"
            )
        unknown = sorted(set(value) - SCENARIO_KEYS)
        if unknown:
            raise ScenarioError(
                f"scenario has unknown fields: {', '.join(unknown)}"
            )
        if not SCENARIO_ID_PATTERN.match(str(value["id"])):
            raise ScenarioError(
                f"scenario id must match {SCENARIO_ID_PATTERN.pattern}: "
                f"{value['id']!r}"
            )
        if not isinstance(value["fixtures"], dict):
            raise ScenarioError("fixtures must be an object")
        if not isinstance(value["assertions"], list) or not value["assertions"]:
            raise ScenarioError("assertions must be a non-empty array")
        assertions = tuple(AssertionSpec.from_dict(item) for item in value["assertions"])
        assertion_ids = [assertion.id for assertion in assertions]
        if len(assertion_ids) != len(set(assertion_ids)):
            raise ScenarioError("assertion ids must be unique")
        tools = value.get("tools")
        if tools is not None:
            if not isinstance(tools, list) or not all(
                isinstance(item, str) for item in tools
            ):
                raise ScenarioError("tools must be an array of tool names")
            tools = tuple(tools)
        output_contract = value.get("output_contract", {})
        if not isinstance(output_contract, dict):
            raise ScenarioError("output_contract must be an object")
        _check_shape_is_published(assertions, output_contract)
        return cls(
            schema_version=str(value["schema_version"]),
            id=str(value["id"]),
            name=str(value["name"]),
            description=str(value["description"]),
            goal=str(value["goal"]),
            fixtures=value["fixtures"],
            assertions=assertions,
            tools=tools,
            output_contract=dict(output_contract),
            limits=dict(value.get("limits", {})),
            metadata=dict(value.get("metadata", {})),
        )

    @classmethod
    def load(cls, path: str | Path) -> "Scenario":
        source = Path(path)
        try:
            value = json.loads(source.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ScenarioError(f"scenario does not exist: {source}") from exc
        except json.JSONDecodeError as exc:
            raise ScenarioError(f"invalid JSON in {source}: {exc}") from exc
        return cls.from_dict(value)

    def public_dict(self) -> dict[str, Any]:
        """
        What the subject is allowed to know before it starts.

        Assertions stay out: a subject that can read the grading criteria is
        not being evaluated. Anything the subject is *required* to do must
        appear here instead, or it is a hidden contract it cannot satisfy.
        """
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "goal": self.goal,
            "output_contract": self.output_contract,
            "limits": self.limits,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class Event:
    sequence: int
    timestamp: str
    kind: str
    target: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventRecorder:
    def __init__(self) -> None:
        self._events: list[Event] = []

    @property
    def events(self) -> tuple[Event, ...]:
        return tuple(self._events)

    def record(
        self,
        kind: str,
        target: str,
        payload: dict[str, Any] | None = None,
    ) -> Event:
        # Payloads carry whatever the subject sent — tool arguments, log
        # lines, artifact bodies — so their nesting is the subject's choice,
        # and every one of them is walked again by `asdict` and the JSON
        # encoder when the bundle is written. Bounding here covers every
        # recorded event at once, rather than each caller remembering to.
        bounded, _ = bound_depth(payload or {})
        event = Event(
            sequence=len(self._events) + 1,
            timestamp=utc_now(),
            kind=kind,
            target=target,
            payload=bounded,
        )
        self._events.append(event)
        return event


@dataclass(frozen=True)
class AssertionResult:
    id: str
    description: str
    passed: bool
    actual: Any
    expected: Any
    message: str
    measured: bool = True
    """
    Whether Beacon could evaluate this assertion at all.

    A subject that finishes without producing the evidence an assertion reads
    leaves nothing to compare. Reporting that as `passed=False` states a
    conclusion about the subject's behavior that was never measured — the
    distinction `docs/architecture.md` draws between *the subject did the wrong
    thing* and *we do not know what the subject did*.

    The runner already applies this when the artifact itself is missing. This
    carries the same rule down to a path inside one: an unreachable path is not
    a failure, it is an absence of evidence, and it resolves the run to
    INCOMPLETE.
    """

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SubjectResult:
    status: str
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


REQUIRED_EVIDENCE_FIELDS = ("run_id", "result")
"""
The two fields a bundle cannot default its way out of.

Everything else in `from_dict` defaults, deliberately: an old bundle staying
readable is the point of writing one. These two cannot. `run_id` is what
identifies a bundle to `--baseline-recent`'s exclusion list, so a defaulted one
lets a run compare against itself. Defaulting `result` would invent a verdict,
and history is exactly what a verdict gets compared against.
"""


@dataclass
class Evidence:
    evidence_version: str
    run_id: str
    started_at: str
    completed_at: str
    scenario: dict[str, Any]
    subject: dict[str, Any]
    result: str
    assertions: list[dict[str, Any]]
    state: dict[str, Any]
    state_diff: dict[str, Any]
    events: list[dict[str, Any]]
    artifacts: dict[str, Any]
    usage: dict[str, Any]
    reset_verified: bool
    limitations: list[str]
    digest: str = ""

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Evidence":
        """
        Rebuild an evidence bundle from disk.

        Every field is taken as written, including the digest, so a bundle can
        be re-read and re-graded without calling the subject again. Fields
        added since a bundle was written default rather than raising: an old
        bundle staying readable is the point of writing one.

        What cannot default raises `ValueError`, and that is the whole failure
        surface of this function. Callers that tolerate an unreadable bundle —
        `load_recent_evidence` is the one that matters — catch that and nothing
        else, so a second error type escaping here is a crash rather than a
        skipped file.
        """
        # A bundle that is not a JSON object at all arrives here as a list or a
        # scalar, and the unknown-field check below then raises TypeError from
        # inside a join: the wrong type, out of a function whose contract is
        # ValueError, from a line that reads like a field check.
        if not isinstance(value, dict):
            raise ValueError(
                f"evidence must be a JSON object, not {type(value).__name__}"
            )
        known = {item.name for item in fields(cls)}
        unknown = sorted(set(value) - known)
        if unknown:
            raise ValueError(
                f"evidence has unknown fields: {', '.join(unknown)}"
            )
        # These used to raise KeyError from the subscripts below, which is not
        # what this function promises and not what its one tolerant caller
        # catches — so a single half-written bundle in the output directory
        # took down a run that had already finished and been graded.
        missing = [name for name in REQUIRED_EVIDENCE_FIELDS if name not in value]
        if missing:
            raise ValueError(
                f"evidence is missing required field(s): {', '.join(missing)}"
            )
        return cls(
            evidence_version=str(value.get("evidence_version", "0.1")),
            run_id=str(value["run_id"]),
            started_at=str(value.get("started_at", "")),
            completed_at=str(value.get("completed_at", "")),
            scenario=dict(value.get("scenario", {})),
            subject=dict(value.get("subject", {})),
            result=str(value["result"]),
            assertions=list(value.get("assertions", [])),
            state=dict(value.get("state", {})),
            state_diff=dict(value.get("state_diff", {})),
            events=list(value.get("events", [])),
            artifacts=dict(value.get("artifacts", {})),
            usage=dict(value.get("usage", {})),
            reset_verified=bool(value.get("reset_verified", False)),
            limitations=list(value.get("limitations", [])),
            digest=str(value.get("digest", "")),
        )

    @classmethod
    def load(cls, path: str | Path) -> "Evidence":
        return cls.from_dict(
            json.loads(Path(path).read_text(encoding="utf-8"))
        )

    def unsigned_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["digest"] = ""
        return value

    def finalize(self) -> None:
        self.digest = canonical_digest(self.unsigned_dict())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
