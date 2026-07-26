from __future__ import annotations

from typing import Any


class ToolArgumentError(ValueError):
    """Raised when tool arguments do not satisfy the tool's declared schema."""


JSON_TYPES: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
    "null": type(None),
}


def _type_name(value: Any) -> str:
    for name, python_type in JSON_TYPES.items():
        if name == "integer" and isinstance(value, bool):
            continue
        if isinstance(value, python_type):
            return name
    return type(value).__name__


def _matches(value: Any, expected: str) -> bool:
    python_type = JSON_TYPES.get(expected)
    if python_type is None:
        return True
    if expected in {"integer", "number"} and isinstance(value, bool):
        return False
    return isinstance(value, python_type)


def validate_arguments(
    tool: str,
    schema: dict[str, Any],
    arguments: dict[str, Any],
) -> None:
    """
    Check arguments against a tool's declared `inputSchema`.

    Services advertise an input schema and then index straight into the
    arguments, so a missing field surfaced as `KeyError: 'in_reply_to'` — the
    same type and shape as `KeyError: message not found`. A subject cannot tell
    "you called this wrong" from "the thing you asked for does not exist", so
    it retries the same call instead of correcting it. Refusing the call with a
    specific message is what makes the difference recoverable.

    Covers the subset the tool definitions actually use: object type, required
    properties, property types, and additionalProperties.
    """
    if not isinstance(arguments, dict):
        raise ToolArgumentError(
            f"{tool} expects an object of arguments, got {_type_name(arguments)}"
        )
    if not schema:
        return

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    missing = [name for name in required if name not in arguments]
    if missing:
        raise ToolArgumentError(
            f"{tool} is missing required argument(s): {', '.join(sorted(missing))}. "
            f"Expected: {', '.join(sorted(properties)) or 'none'}"
        )

    if schema.get("additionalProperties") is False:
        unexpected = sorted(set(arguments) - set(properties))
        if unexpected:
            raise ToolArgumentError(
                f"{tool} does not accept argument(s): {', '.join(unexpected)}. "
                f"Accepted: {', '.join(sorted(properties)) or 'none'}"
            )

    for name, value in arguments.items():
        expected = properties.get(name, {}).get("type")
        if expected and not _matches(value, str(expected)):
            raise ToolArgumentError(
                f"{tool} argument '{name}' must be {expected}, "
                f"got {_type_name(value)}"
            )
