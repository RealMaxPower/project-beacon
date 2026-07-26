#!/usr/bin/env python3
"""
Control: raises partway through, after mutating state.

A draft exists when the process dies, so the state assertions could plausibly
be satisfied. They must not decide the verdict: the subject never finished, so
the result is INCOMPLETE regardless of what the state looks like.
"""

from __future__ import annotations

import _bridge as bridge


def main() -> int:
    bridge.start()
    headers = bridge.action_required()
    message = bridge.tool_call(
        "read-001",
        "mail_read_message",
        {"message_id": headers[0]["id"]},
    )
    bridge.tool_call(
        "draft-001",
        "mail_create_draft",
        {
            "to": message["sender"],
            "subject": f"Re: {message['subject']}",
            "body": "Partial work.",
            "in_reply_to": message["id"],
        },
    )
    raise RuntimeError("simulated agent crash before completion")


if __name__ == "__main__":
    raise SystemExit(main())
