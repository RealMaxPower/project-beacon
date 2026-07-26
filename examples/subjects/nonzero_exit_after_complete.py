#!/usr/bin/env python3
"""
Does the task correctly, reports `complete`, then exits with a non-zero code.

A wrapper script whose cleanup fails, an atexit handler that raises, a runtime
that returns its own status code — the work is done and Beacon has been told
so. Exit status after a valid `complete` is worth recording, but it does not
retract the completion.
"""

from __future__ import annotations

import _bridge as bridge


def main() -> int:
    bridge.start()
    handled = bridge.brief_and_draft()
    bridge.artifact("summary", bridge.briefing_text(handled))
    bridge.complete(f"Prepared {len(handled)} draft responses.")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
