from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
        event = Event(
            sequence=len(self._events) + 1,
            timestamp=utc_now(),
            kind=kind,
            target=target,
            payload=payload or {},
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
    reset_verified: bool
    limitations: list[str]
    digest: str = ""

    def unsigned_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["digest"] = ""
        return value

    def finalize(self) -> None:
        self.digest = canonical_digest(self.unsigned_dict())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
