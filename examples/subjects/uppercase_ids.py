#!/usr/bin/env python3
"""
Does the task correctly and cites message ids in uppercase.

Models routinely normalise identifiers when writing prose. The citation
assertion uses Python's `in` against the artifact text, which is
case-sensitive, so "M-001" does not satisfy a check for "m-001".
"""

from __future__ import annotations

import _bridge as bridge


def main() -> int:
    bridge.start()
    handled = bridge.brief_and_draft()
    bridge.artifact("summary", bridge.briefing_text(handled, cite="{id}").upper())
    bridge.complete(f"Prepared {len(handled)} draft responses.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
