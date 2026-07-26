#!/usr/bin/env python3
"""
A reference MCP host: connects to Beacon's façade and completes the scenario.

Beacon starts the façade and launches this process, which reads where to
connect from its environment (or from the generated config file), speaks
MCP over HTTP, and finishes by calling `beacon_submit`.

    python3 -m beacon run scenarios/inbox-briefing/scenario.json \
      --adapter mcp-host \
      --command "python3 examples/mcp_host_agent.py"

It hardcodes nothing about the scenario: the goal arrives in BEACON_GOAL and
the tool surface comes from `tools/list`. Only stdlib — no MCP SDK — so it
doubles as a specification of the wire traffic a real host produces.

A model-backed host would replace `decide` with a model call. Everything
around it — the transport, the tool loop, the submission — is unchanged.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

PROTOCOL_VERSION = "2025-06-18"


class MCPHTTPClient:
    """Minimal Streamable-HTTP MCP client: initialize, tools/list, tools/call."""

    def __init__(self, url: str, token: str, timeout: float = 30.0) -> None:
        self._url = url
        self._token = token
        self._timeout = timeout
        self._next_id = 0
        self.session_id: str | None = None

    def _post(self, message: dict[str, Any]) -> dict[str, Any] | None:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self._token}",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        request = urllib.request.Request(
            self._url,
            data=json.dumps(message).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self._timeout) as response:
            self.session_id = response.headers.get("Mcp-Session-Id", self.session_id)
            if response.status == 202:
                return None
            return json.loads(response.read().decode("utf-8"))

    def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._next_id += 1
        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params
        response = self._post(message)
        if response is None:
            raise RuntimeError(f"no response to {method}")
        if "error" in response:
            raise RuntimeError(f"MCP error for {method}: {response['error']}")
        return response["result"]

    def notify(self, method: str) -> None:
        self._post({"jsonrpc": "2.0", "method": method})

    def initialize(self) -> dict[str, Any]:
        result = self.request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {
                    "name": "beacon-reference-mcp-host",
                    "version": "0.1.0",
                },
            },
        )
        self.notify("notifications/initialized")
        return result

    def list_tools(self) -> list[dict[str, Any]]:
        return self.request("tools/list", {})["tools"]

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        result = self.request("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            text = "".join(
                block.get("text", "") for block in result.get("content", [])
            )
            raise RuntimeError(text or "tool call failed")
        structured = result.get("structuredContent")
        if structured is not None:
            return structured.get("result")
        return "".join(block.get("text", "") for block in result.get("content", []))


def decide(client: MCPHTTPClient, available: set[str]) -> tuple[str, int]:
    """
    Do the work. A model-backed host would put a model here instead.

    Only tools the server actually offered are used — the same discipline a
    real host follows, and what makes this exercise the scenario's tool scope.
    """
    if "mail_list_messages" not in available:
        return "No inbox tools were offered; nothing to do.", 0

    headers = client.call("mail_list_messages", {})
    action_required = [
        header
        for header in headers
        if "action_required" in header.get("labels", [])
        and not header.get("protected")
    ]

    lines = []
    for header in action_required:
        message = client.call("mail_read_message", {"message_id": header["id"]})
        lines.append(
            f"- [{message['id']}] {message['subject']} — {message['body']}"
        )
        if "mail_create_draft" in available:
            client.call(
                "mail_create_draft",
                {
                    "to": message["sender"],
                    "subject": f"Re: {message['subject']}",
                    "body": (
                        "Thanks for the note. I reviewed it and will confirm "
                        "the requested next step after a human review."
                    ),
                    "in_reply_to": message["id"],
                },
            )
    briefing = "Action-required inbox briefing\n\n" + "\n".join(lines)
    return briefing, len(action_required)


def main() -> int:
    url = os.environ.get("BEACON_MCP_URL")
    token = os.environ.get("BEACON_MCP_TOKEN")
    if not url or not token:
        print("BEACON_MCP_URL and BEACON_MCP_TOKEN are required", file=sys.stderr)
        return 2

    client = MCPHTTPClient(url, token)
    client.initialize()
    tools = client.list_tools()
    available = {tool["name"] for tool in tools}

    briefing, handled = decide(client, available)

    if "beacon_submit" in available:
        client.call(
            "beacon_submit",
            {
                "status": "completed",
                "summary": f"Prepared {handled} draft responses.",
                "artifact": briefing,
            },
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as exc:  # pragma: no cover - transport failure
        print(f"could not reach Beacon's MCP server: {exc}", file=sys.stderr)
        raise SystemExit(1)
