#!/usr/bin/env python3
"""
Control: does the work, then hangs without sending `complete`.

A wedged model call or a subject waiting on input that never arrives. The state
assertions would all pass, which is precisely why the verdict must be
INCOMPLETE — "not run to completion" can never be a pass.
"""

from __future__ import annotations

import time

import _bridge as bridge

HANG_SECONDS = 3600


def main() -> int:
    bridge.start()
    handled = bridge.brief_and_draft()
    bridge.artifact("summary", bridge.briefing_text(handled))
    time.sleep(HANG_SECONDS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
