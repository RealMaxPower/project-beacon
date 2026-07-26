#!/usr/bin/env python3
"""
Does the task correctly, then takes three seconds to shut down.

Closing an HTTP connection pool, joining a non-daemon thread, or flushing an
SDK client all take time. The work is finished and `complete` has been sent
before any of it starts.

Beacon currently allows two seconds after `complete`, then terminates the
process and reports the resulting signal as a subject error.
"""

from __future__ import annotations

import time

import _bridge as bridge

TEARDOWN_SECONDS = 3


def main() -> int:
    bridge.start()
    handled = bridge.brief_and_draft()
    bridge.artifact("summary", bridge.briefing_text(handled))
    bridge.complete(f"Prepared {len(handled)} draft responses.")
    time.sleep(TEARDOWN_SECONDS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
