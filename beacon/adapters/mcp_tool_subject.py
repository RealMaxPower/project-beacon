from __future__ import annotations

from typing import Any

from beacon.adapters.base import ExecutionContext
from beacon.models import SubjectResult
from beacon.protocols.mcp import MCPError
from beacon.protocols.mcp_http import MCPHTTPClient
from beacon.usage import UsageLimitExceeded


class MCPToolSubjectAdapter:
    """
    Grades one tool on a hosted MCP server as the subject.

    Many published MCP servers are agents in everything but name: the tool
    behind `ask_question` or `query-docs` runs a model, reads sources, and
    returns claims. Beacon could inspect such a server's manifest but never
    grade what it said, so a whole population of deployed agents sat outside
    the harness.

    The evidence shape is the same as the A2A adapter's and for the same
    reason: the subject calls its own tools against its own corpus, so there
    is no synthetic state to diff. What can be graded is the answer.

    One call per run, and the scenario's `max_subject_calls` bounds it. These
    are other people's paid services.
    """

    def __init__(
        self,
        url: str,
        tool: str,
        arguments: dict[str, Any],
        *,
        name: str | None = None,
        timeout_seconds: float | None = None,
        authorization: str | None = None,
        artifact_name: str = "answer",
    ) -> None:
        self._url = url
        self._tool = tool
        self._arguments = dict(arguments)
        self._name = name or url
        self._timeout_seconds = timeout_seconds
        self._authorization = authorization
        self._artifact_name = artifact_name

    @property
    def descriptor(self) -> dict[str, Any]:
        return {
            "id": "mcp-tool",
            "name": self._name,
            "adapter": "mcp-tool",
            "integration_level": 1,
            "server_url": self._url,
            "tool": self._tool,
        }

    @staticmethod
    def _flatten(result: dict[str, Any]) -> str:
        """Reduce a tools/call result to the text a scenario can assert on."""
        parts: list[str] = []
        for block in result.get("content") or []:
            if block.get("type") == "text" and block.get("text"):
                parts.append(str(block["text"]))
        structured = result.get("structuredContent")
        if structured is not None:
            import json as _json

            parts.append(_json.dumps(structured, ensure_ascii=False))
        return "\n".join(parts)

    def execute(self, context: ExecutionContext) -> SubjectResult:
        limits = context.scenario.limits
        timeout = float(
            self._timeout_seconds
            if self._timeout_seconds is not None
            else limits.get("timeout_seconds", 60)
        )
        client = MCPHTTPClient(
            self._url, timeout_seconds=timeout, authorization=self._authorization
        )
        try:
            with context.usage.timed("mcp_initialize", self._url):
                client.start()
        except (MCPError, UsageLimitExceeded) as exc:
            context.recorder.record(
                "subject_error", "mcp-tool", {"stage": "initialize", "message": str(exc)}
            )
            return SubjectResult(status="error", error=f"handshake failed: {exc}")

        context.recorder.record(
            "mcp_server_info",
            self._url,
            {
                "server": client.server_info,
                "protocol_version": client.protocol_version,
                "capabilities": client.capabilities,
            },
        )

        try:
            with context.usage.timed("mcp_tool_call", self._tool) as timer:
                result = client.call_tool(self._tool, self._arguments)
                timer.detail["tool"] = self._tool
        except UsageLimitExceeded as exc:
            context.recorder.record("usage_limit", "mcp-tool", {"message": str(exc)})
            return SubjectResult(status="budget_exceeded", error=str(exc))
        except MCPError as exc:
            context.recorder.record(
                "subject_error", "mcp-tool", {"stage": "call", "message": str(exc)}
            )
            return SubjectResult(status="error", error=str(exc))

        # MCP carries server-supplied extras under `_meta`, which `_flatten`
        # drops along with everything that is not the answer. A usage key there
        # is the server declaring what the call cost it.
        meta = result.get("_meta")
        if isinstance(meta, dict):
            context.usage.report("mcp", meta.get("usage"))

        text = self._flatten(result)
        context.add_artifact(self._artifact_name, text)
        context.recorder.record(
            "mcp_tool_result",
            self._tool,
            {
                "is_error": bool(result.get("isError")),
                "characters": len(text),
            },
        )

        if result.get("isError"):
            # The server answered correctly by refusing. That is a statement
            # about the request, not evidence the agent behaved badly.
            return SubjectResult(
                status="tool_error",
                error=f"{self._tool} returned an error result",
                metadata={"server": client.server_info},
            )
        return SubjectResult(
            status="completed",
            summary=f"{self._tool} returned {len(text)} characters.",
            metadata={
                "server": client.server_info,
                "protocol_version": client.protocol_version,
            },
        )
