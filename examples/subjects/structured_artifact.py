#!/usr/bin/env python3
"""
Does the task correctly and returns the briefing as structured JSON.

The artifact channel accepts any JSON value, and a structured briefing is
arguably better output than prose. But `contains` runs `expected in actual`,
and on a dict that tests the *keys*, so every citation check fails.
"""

from __future__ import annotations

import _bridge as bridge


def main() -> int:
    bridge.start()
    handled = bridge.brief_and_draft()
    bridge.artifact(
        "summary",
        {
            "title": "Action-required inbox briefing",
            "items": [
                {
                    "message_id": message["id"],
                    "subject": message["subject"],
                    "detail": message["body"],
                }
                for message in handled
            ],
        },
    )
    bridge.complete(f"Prepared {len(handled)} draft responses.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
