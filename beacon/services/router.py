from __future__ import annotations

from typing import Any, Iterable

from beacon.models import EventRecorder
from beacon.toolschema import validate_arguments, validate_tool_name


class ToolRouter:
    """
    Routes tool calls to services, restricted to the scenario's tool surface.

    A scenario that offers a tool must tolerate its use. Scoping is how a
    scenario forbids an action without setting a trap: an unoffered tool is
    never advertised to the subject and is refused if called anyway.
    """

    def __init__(
        self,
        recorder: EventRecorder,
        *,
        allowed: Iterable[str] | None = None,
    ) -> None:
        self._recorder = recorder
        self._services: list[Any] = []
        self._allowed = None if allowed is None else frozenset(allowed)

    def register(self, service: Any) -> None:
        # Checked here rather than at publish time: a name that cannot reach a
        # model is a defect in the service, and the run should fail while
        # wiring up rather than on the subject's first tool call.
        for definition in service.definitions():
            validate_tool_name(definition["name"])
        self._services.append(service)

    def is_allowed(self, tool: str) -> bool:
        return self._allowed is None or tool in self._allowed

    def definitions(self) -> list[dict[str, Any]]:
        definitions: list[dict[str, Any]] = []
        for service in self._services:
            definitions.extend(
                definition
                for definition in service.definitions()
                if self.is_allowed(definition["name"])
            )
        return definitions

    def unknown_tools(self) -> tuple[str, ...]:
        """Scoped names no registered service provides, for validation."""
        if self._allowed is None:
            return ()
        provided = {
            definition["name"]
            for service in self._services
            for definition in service.definitions()
        }
        return tuple(sorted(self._allowed - provided))

    def call(
        self,
        tool: str,
        arguments: dict[str, Any],
        *,
        call_id: str | None = None,
    ) -> Any:
        payload = {
            "call_id": call_id,
            "arguments": arguments,
        }
        # Recorded before dispatch, and before the scope check, so that an
        # attempt to use a forbidden tool is evidence even though it never ran.
        self._recorder.record("tool_call", tool, payload)
        if not self.is_allowed(tool):
            self._recorder.record(
                "tool_error",
                tool,
                {
                    "call_id": call_id,
                    "error_type": "ToolNotAvailable",
                    "message": f"tool is not in this scenario's surface: {tool}",
                },
            )
            raise KeyError(f"tool is not available: {tool}")
        for service in self._services:
            schemas = {
                definition["name"]: definition.get("inputSchema", {})
                for definition in service.definitions()
            }
            if tool not in schemas:
                continue
            try:
                validate_arguments(tool, schemas[tool], arguments)
                result = service.call(tool, arguments)
            except Exception as exc:
                self._recorder.record(
                    "tool_error",
                    tool,
                    {
                        "call_id": call_id,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    },
                )
                raise
            self._recorder.record(
                "tool_result",
                tool,
                {
                    "call_id": call_id,
                    "result": result,
                },
            )
            return result
        self._recorder.record(
            "tool_error",
            tool,
            {
                "call_id": call_id,
                "error_type": "UnknownTool",
                "message": f"unknown tool: {tool}",
            },
        )
        raise KeyError(f"unknown tool: {tool}")

