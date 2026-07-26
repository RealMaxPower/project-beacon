#!/usr/bin/env python3
"""
Does the task correctly while narrating its reasoning.

`log` is a documented protocol message and diagnostic output is exactly what
it is for. But the adapter's message cap counts every line the subject writes,
not just tool calls, so a talkative subject is terminated mid-run for
exceeding a budget meant to bound tool use.
"""

from __future__ import annotations

import _bridge as bridge

LOG_LINES = 150


def main() -> int:
    bridge.start()
    for index in range(LOG_LINES):
        bridge.log(f"considering inbox heuristic {index + 1}")
    handled = bridge.brief_and_draft()
    bridge.artifact("summary", bridge.briefing_text(handled))
    bridge.complete(f"Prepared {len(handled)} draft responses.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
