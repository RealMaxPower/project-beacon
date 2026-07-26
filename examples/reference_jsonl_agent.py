#!/usr/bin/env python3
"""
Reference external subject for Beacon's bidirectional JSONL adapter.

The script intentionally has no dependency on the Beacon package. It shows the
small bridge a CLI, HTTP wrapper, or SDK wrapper must implement.
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


def main() -> int:
    start = receive()
    if start.get("type") != "start":
        raise RuntimeError("first Beacon message must be start")

    messages = tool_call("list-001", "mail.list_messages", {})
    action_messages = [
        message
        for message in messages
        if "action_required" in message.get("labels", [])
    ]
    lines: list[str] = []
    for index, header in enumerate(action_messages, start=1):
        message = tool_call(
            f"read-{index:03d}",
            "mail.read_message",
            {"message_id": header["id"]},
        )
        lines.append(f"- [{message['id']}] {message['subject']} — {message['body']}")
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

    send(
        {
            "type": "artifact",
            "name": "summary",
            "content": "Action-required inbox briefing\n\n" + "\n".join(lines),
        }
    )
    send(
        {
            "type": "complete",
            "status": "completed",
            "summary": f"Prepared {len(action_messages)} draft responses.",
            "metadata": {"action_messages": len(action_messages)},
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

