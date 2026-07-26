"""
Minimal helpers for the adversarial subject suite.

Deliberately has no dependency on the `beacon` package: these subjects speak
the documented JSONL bridge protocol and nothing else, exactly as a real
external agent would. See `docs/protocol-contracts.md`.
"""

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
    send(
        {
            "type": "tool_call",
            "id": call_id,
            "tool": tool,
            "arguments": arguments,
        }
    )
    response = receive()
    if response.get("type") != "tool_result" or response.get("id") != call_id:
        raise RuntimeError(f"unexpected tool response: {response}")
    if not response.get("ok"):
        raise RuntimeError(str(response.get("error")))
    return response.get("result")


def log(message: str, level: str = "info") -> None:
    send({"type": "log", "level": level, "message": message})


def artifact(name: str, content: Any) -> None:
    send({"type": "artifact", "name": name, "content": content})


def complete(summary: str, status: str = "completed", **extra: Any) -> None:
    send({"type": "complete", "status": status, "summary": summary, **extra})


def action_required() -> list[dict[str, Any]]:
    """The visible messages a briefing is expected to act on."""
    messages = tool_call("list-001", "mail.list_messages", {})
    return [m for m in messages if "action_required" in m.get("labels", [])]


def brief_and_draft(*, cite: str = "{id}") -> list[dict[str, Any]]:
    """
    The competent baseline: read each action-required message, cite it in the
    briefing, and draft a reply. `cite` controls how the message id is written.
    """
    handled: list[dict[str, Any]] = []
    for index, header in enumerate(action_required(), start=1):
        message = tool_call(
            f"read-{index:03d}",
            "mail.read_message",
            {"message_id": header["id"]},
        )
        tool_call(
            f"draft-{index:03d}",
            "mail.create_draft",
            {
                "to": message["sender"],
                "subject": f"Re: {message['subject']}",
                "body": (
                    "Thanks for the note. I reviewed it and will confirm the "
                    "requested next step after a human review."
                ),
                "in_reply_to": message["id"],
            },
        )
        handled.append(message)
    return handled


def briefing_text(messages: list[dict[str, Any]], *, cite: str = "{id}") -> str:
    lines = [
        f"- [{cite.format(id=message['id'])}] {message['subject']} "
        f"— {message['body']}"
        for message in messages
    ]
    return "Action-required inbox briefing\n\n" + "\n".join(lines)
