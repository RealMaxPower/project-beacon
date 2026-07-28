from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


"""
Check an agent's output against a shape the scenario declares.

Distinct from `toolschema.py`, which guards arguments coming *in* to a tool
and raises on the first problem so the call can be refused. This one grades
output going *out*, so it does the opposite in two ways: it walks the whole
document and reports every violation at once, because a builder fixing their
agent's output wants the list rather than one item per run; and it never
raises on the value being checked, because a badly shaped answer is a verdict,
not a crash.
"""


class SchemaError(ValueError):
    """Raised when the declared schema itself is not usable."""


SUPPORTED_KEYWORDS = frozenset(
    {
        "type",
        "properties",
        "required",
        "additionalProperties",
        "items",
        "enum",
        "const",
        "minLength",
        "maxLength",
        "pattern",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minimum",
        "maximum",
        "description",
    }
)

JSON_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
    "null": type(None),
}


@dataclass(frozen=True)
class SchemaViolation:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "message": self.message}


def type_name(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    for name, python_type in JSON_TYPES.items():
        if name in {"integer", "number", "boolean"}:
            continue
        if isinstance(value, python_type):
            return name
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return type(value).__name__


def _is_type(value: Any, expected: str) -> bool:
    python_type = JSON_TYPES.get(expected)
    if python_type is None:
        return True
    # In JSON Schema a boolean is not an integer, but in Python it is a
    # subclass of int, so `True` would satisfy "integer" without this.
    if isinstance(value, bool):
        return expected == "boolean"
    if expected == "integer" and isinstance(value, float):
        return value.is_integer()
    return isinstance(value, python_type)


def validate_schema(schema: Any, *, path: str = "schema") -> None:
    """
    Check the declared schema before anything is graded against it.

    An unrecognised keyword is refused rather than ignored. `minlength` for
    `minLength` would otherwise constrain nothing while reading as though it
    did, and the passing run that followed would be evidence of nothing.
    """
    if not isinstance(schema, dict):
        raise SchemaError(f"{path} must be an object, got {type_name(schema)}")

    unknown = sorted(set(schema) - SUPPORTED_KEYWORDS)
    if unknown:
        raise SchemaError(
            f"{path} uses unsupported keyword(s): {', '.join(unknown)}. "
            f"Supported: {', '.join(sorted(SUPPORTED_KEYWORDS))}"
        )

    declared = schema.get("type")
    if declared is not None:
        names = declared if isinstance(declared, list) else [declared]
        for name in names:
            if name not in JSON_TYPES:
                raise SchemaError(
                    f"{path}.type has unknown type {name!r}. "
                    f"Known: {', '.join(sorted(JSON_TYPES))}"
                )

    for keyword in ("enum",):
        if keyword in schema and not isinstance(schema[keyword], list):
            raise SchemaError(f"{path}.{keyword} must be an array")

    if "required" in schema:
        if not isinstance(schema["required"], list):
            raise SchemaError(f"{path}.required must be an array of property names")
        properties = schema.get("properties", {})
        if isinstance(properties, dict):
            # Requiring a property the schema never describes is always an
            # authoring slip, and it makes the assertion unsatisfiable.
            undescribed = sorted(set(schema["required"]) - set(properties))
            if undescribed and schema.get("additionalProperties") is False:
                raise SchemaError(
                    f"{path}.required names {', '.join(undescribed)}, which "
                    f"{path}.properties does not describe and "
                    f"additionalProperties forbids"
                )

    if "pattern" in schema:
        try:
            re.compile(str(schema["pattern"]))
        except re.error as error:
            raise SchemaError(f"{path}.pattern is not a valid regex: {error}") from error

    properties = schema.get("properties")
    if properties is not None:
        if not isinstance(properties, dict):
            raise SchemaError(f"{path}.properties must be an object")
        for name, subschema in properties.items():
            validate_schema(subschema, path=f"{path}.properties.{name}")

    items = schema.get("items")
    if items is not None:
        validate_schema(items, path=f"{path}.items")


def _violations(value: Any, schema: dict[str, Any], path: str) -> list[SchemaViolation]:
    found: list[SchemaViolation] = []

    declared = schema.get("type")
    if declared is not None:
        names = declared if isinstance(declared, list) else [declared]
        if not any(_is_type(value, str(name)) for name in names):
            return [
                SchemaViolation(
                    path,
                    f"expected {' or '.join(str(name) for name in names)}, "
                    f"got {type_name(value)}",
                )
            ]

    if "const" in schema and value != schema["const"]:
        found.append(SchemaViolation(path, f"expected {schema['const']!r}"))

    if "enum" in schema and value not in schema["enum"]:
        allowed = ", ".join(repr(item) for item in schema["enum"])
        found.append(SchemaViolation(path, f"{value!r} is not one of: {allowed}"))

    if isinstance(value, str):
        if "minLength" in schema and len(value) < int(schema["minLength"]):
            found.append(
                SchemaViolation(
                    path, f"is {len(value)} characters, minimum {schema['minLength']}"
                )
            )
        if "maxLength" in schema and len(value) > int(schema["maxLength"]):
            found.append(
                SchemaViolation(
                    path, f"is {len(value)} characters, maximum {schema['maxLength']}"
                )
            )
        if "pattern" in schema and not re.search(str(schema["pattern"]), value):
            found.append(
                SchemaViolation(path, f"does not match /{schema['pattern']}/")
            )

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            found.append(SchemaViolation(path, f"is below minimum {schema['minimum']}"))
        if "maximum" in schema and value > schema["maximum"]:
            found.append(SchemaViolation(path, f"is above maximum {schema['maximum']}"))

    if isinstance(value, list):
        if "minItems" in schema and len(value) < int(schema["minItems"]):
            found.append(
                SchemaViolation(
                    path, f"has {len(value)} items, minimum {schema['minItems']}"
                )
            )
        if "maxItems" in schema and len(value) > int(schema["maxItems"]):
            found.append(
                SchemaViolation(
                    path, f"has {len(value)} items, maximum {schema['maxItems']}"
                )
            )
        if schema.get("uniqueItems") is True:
            seen: list[Any] = []
            for item in value:
                if item in seen:
                    found.append(SchemaViolation(path, f"has a duplicate item {item!r}"))
                    break
                seen.append(item)
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                found.extend(_violations(item, item_schema, f"{path}[{index}]"))

    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                found.append(SchemaViolation(_join(path, name), "is required but missing"))
        if schema.get("additionalProperties") is False:
            for name in sorted(set(value) - set(properties)):
                found.append(
                    SchemaViolation(_join(path, name), "is not an accepted property")
                )
        if isinstance(properties, dict):
            for name, subschema in properties.items():
                if name in value and isinstance(subschema, dict):
                    found.extend(
                        _violations(value[name], subschema, _join(path, name))
                    )

    return found


def _join(path: str, name: str) -> str:
    return name if path in {"", "$"} else f"{path}.{name}"


def validate_output(value: Any, schema: dict[str, Any]) -> list[SchemaViolation]:
    """Every way `value` departs from `schema`, rather than only the first."""
    return _violations(value, schema, "$")


def describe_schema(schema: dict[str, Any]) -> str:
    """
    A one-line, human-readable summary of the shape, for a goal or a report.

    A subject cannot satisfy a contract it was never told about. The scenario's
    output contract is published to the subject; this renders the schema into
    something a model can act on without being handed the assertion itself.
    """
    if not isinstance(schema, dict):
        return "any value"
    declared = schema.get("type")
    if declared == "object" or "properties" in schema:
        properties = schema.get("properties", {})
        required = set(schema.get("required", []))
        parts = []
        for name, subschema in properties.items():
            shape = describe_schema(subschema) if isinstance(subschema, dict) else "any"
            mark = "" if name in required else "?"
            parts.append(f"{name}{mark}: {shape}")
        inner = ", ".join(parts) or "any properties"
        return "{" + inner + "}"
    if declared == "array":
        items = schema.get("items")
        inner = describe_schema(items) if isinstance(items, dict) else "any"
        return f"array of {inner}"
    if "enum" in schema:
        return "one of " + "|".join(str(item) for item in schema["enum"])
    return str(declared or "any")
