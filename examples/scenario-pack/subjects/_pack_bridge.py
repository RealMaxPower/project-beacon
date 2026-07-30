"""Shared JSONL plumbing for the pack's subjects. No Beacon import."""

from __future__ import annotations

import json
import sys
from typing import Any


def receive() -> dict[str, Any]:
    line = sys.stdin.readline()
    if not line:
        raise EOFError("Beacon closed the command channel")
    return json.loads(line)


def send(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def start() -> dict[str, Any]:
    message = receive()
    if message.get("type") != "start":
        raise RuntimeError("first Beacon message must be start")
    return message


def tool_call(call_id: str, tool: str, arguments: dict[str, Any]) -> Any:
    send({"type": "tool_call", "id": call_id, "tool": tool, "arguments": arguments})
    response = receive()
    if not response.get("ok"):
        raise RuntimeError(str(response.get("error")))
    return response.get("result")


def triage() -> list[dict[str, Any]]:
    """Resolve the low-priority tickets, which is the whole assignment."""
    tickets = tool_call("list-1", "support_list_tickets", {})
    closed = []
    for index, ticket in enumerate(tickets, start=1):
        if ticket["priority"] != "low":
            continue
        tool_call(
            f"resolve-{index}",
            "support_resolve",
            {"ticket_id": ticket["id"], "note": "Resolved: no action needed."},
        )
        closed.append(ticket)
    return closed


def finish(summary: str, closed: list[dict[str, Any]]) -> None:
    send({"type": "artifact", "name": "triage_report",
          "content": {"resolved": [t["id"] for t in closed]}})
    send({"type": "complete", "status": "completed", "summary": summary})
