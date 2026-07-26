#!/usr/bin/env python3
"""
Control: does exactly what the scenario asks and nothing else.

If this subject stops passing, the harness itself has regressed.
"""

from __future__ import annotations

import _bridge as bridge


def main() -> int:
    bridge.start()
    handled = bridge.brief_and_draft()
    bridge.artifact("summary", bridge.briefing_text(handled))
    bridge.complete(f"Prepared {len(handled)} draft responses.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
