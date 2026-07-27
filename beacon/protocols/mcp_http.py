from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

from beacon.protocols.mcp import MCPError


USER_AGENT = "project-beacon/0.1"
PROTOCOL_VERSION = "2025-06-18"
MAX_REDIRECTS = 3


def _ssl_context() -> ssl.SSLContext | None:
    """Fall back to certifi when the interpreter ships no CA store."""
    paths = ssl.get_default_verify_paths()
    if paths.cafile or paths.capath:
        return None
    try:
        import certifi
    except ImportError:
        return None
    return ssl.create_default_context(cafile=certifi.where())


def _parse_sse(payload: str) -> list[dict[str, Any]]:
    """
    Pull JSON-RPC messages out of an SSE body.

    Streamable HTTP lets a server answer a POST with either `application/json`
    or `text/event-stream`, and which one you get is the server's choice, not
    the client's. A client that only understands JSON silently fails against
    every server that picks the other.
    """
    messages: list[dict[str, Any]] = []
    data_lines: list[str] = []
    for line in payload.splitlines():
        if line.startswith("data:"):
            data_lines.append(line[5:].strip())
            continue
        if not line.strip() and data_lines:
            try:
                messages.append(json.loads("".join(data_lines)))
            except json.JSONDecodeError:
                pass
            data_lines = []
    if data_lines:
        try:
            messages.append(json.loads("".join(data_lines)))
        except json.JSONDecodeError:
            pass
    return messages


class MCPHTTPClient:
    """
    Minimal Streamable-HTTP MCP client, for servers hosted on the web.

    Beacon could only speak MCP over stdio, which meant every hosted server —
    the large majority of what is actually published — was unreachable. The
    surface here matches `MCPStdioClient` deliberately: initialize,
    tools/list, tools/call, and nothing else, so a caller can hold either.

    Sends no tool calls of its own. Inspecting a stranger's server should cost
    them one metadata request, not a side effect.
    """

    def __init__(
        self,
        url: str,
        *,
        timeout_seconds: float = 20.0,
        authorization: str | None = None,
        protocol_version: str = PROTOCOL_VERSION,
    ) -> None:
        if not url.startswith(("http://", "https://")):
            raise ValueError("MCP URL must use http or https")
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.authorization = authorization
        self.protocol_version = protocol_version
        self.session_id: str | None = None
        self.server_info: dict[str, Any] = {}
        self.capabilities: dict[str, Any] = {}
        self._request_id = 0

    def __enter__(self) -> "MCPHTTPClient":
        self.start()
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def _post(self, message: dict[str, Any], _redirects: int = 0) -> dict[str, Any] | None:
        headers = {
            "Content-Type": "application/json",
            # Both are advertised because the server picks.
            "Accept": "application/json, text/event-stream",
            "User-Agent": USER_AGENT,
            "MCP-Protocol-Version": self.protocol_version,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        if self.authorization:
            headers["Authorization"] = self.authorization
        request = urllib.request.Request(
            self.url,
            data=json.dumps(message).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout_seconds, context=_ssl_context()
            ) as response:
                self.session_id = response.headers.get(
                    "Mcp-Session-Id", self.session_id
                )
                content_type = response.headers.get("Content-Type", "")
                body = response.read().decode("utf-8", "replace")
                status = response.status
        except urllib.error.HTTPError as exc:
            # urllib will not follow 307/308 for a POST, so a server that
            # redirects — to add a trailing slash, or to a canonical host —
            # looks unreachable rather than movable. These codes require the
            # method and body to be preserved, so following them is safe.
            if exc.code in {307, 308} and _redirects < MAX_REDIRECTS:
                location = exc.headers.get("Location")
                if location:
                    self.url = urllib.parse.urljoin(self.url, location)
                    return self._post(message, _redirects + 1)
            detail = ""
            if exc.fp:
                detail = exc.read(300).decode("utf-8", "replace")
            raise MCPError(
                f"HTTP {exc.code} from {self.url}: {detail[:200]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise MCPError(f"could not reach {self.url}: {exc.reason}") from exc

        if status == 202 or not body.strip():
            return None
        if "text/event-stream" in content_type:
            messages = _parse_sse(body)
            if not messages:
                raise MCPError(f"no JSON-RPC message in the SSE body from {self.url}")
            return messages[-1]
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise MCPError(
                f"non-JSON response from {self.url} "
                f"(content-type {content_type!r}): {body[:160]!r}"
            ) from exc

    def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._request_id += 1
        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params
        response = self._post(message)
        if response is None:
            raise MCPError(f"no response to {method} from {self.url}")
        if "error" in response:
            raise MCPError(f"MCP error for {method}: {response['error']}")
        if "result" not in response:
            raise MCPError(f"MCP response for {method} omitted result")
        return response["result"]

    def notify(self, method: str) -> None:
        self._post({"jsonrpc": "2.0", "method": method})

    def start(self) -> None:
        result = self.request(
            "initialize",
            {
                "protocolVersion": self.protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "project-beacon", "version": "0.1.0"},
            },
        )
        negotiated = result.get("protocolVersion")
        if not negotiated:
            raise MCPError("MCP initialize response omitted protocolVersion")
        self.protocol_version = str(negotiated)
        self.server_info = dict(result.get("serverInfo", {}))
        self.capabilities = dict(result.get("capabilities", {}))
        try:
            self.notify("notifications/initialized")
        except MCPError:
            # Some servers reject the notification but work regardless; the
            # handshake has already succeeded by this point.
            pass

    def list_tools(self) -> list[dict[str, Any]]:
        result = self.request("tools/list", {})
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            raise MCPError("tools/list result must contain a tools array")
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self.request(
            "tools/call", {"name": name, "arguments": arguments}
        )
        if not isinstance(result, dict):
            raise MCPError("tools/call result must be an object")
        return result
