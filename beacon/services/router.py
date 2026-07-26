from __future__ import annotations

from typing import Any

from beacon.models import EventRecorder


class ToolRouter:
    def __init__(self, recorder: EventRecorder) -> None:
        self._recorder = recorder
        self._services: list[Any] = []

    def register(self, service: Any) -> None:
        self._services.append(service)

    def definitions(self) -> list[dict[str, Any]]:
        definitions: list[dict[str, Any]] = []
        for service in self._services:
            definitions.extend(service.definitions())
        return definitions

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
        self._recorder.record("tool_call", tool, payload)
        for service in self._services:
            known = {definition["name"] for definition in service.definitions()}
            if tool not in known:
                continue
            try:
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

