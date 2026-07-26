#!/usr/bin/env python3
"""
Does the task correctly and calls its output `briefing`.

The goal says "Produce a concise briefing". The assertions read
`artifacts.summary`. Nothing Beacon sends this subject mentions the name
`summary` — `Scenario.public_dict()` omits the assertions entirely.

A missing declared artifact means Beacon could not collect the evidence it
needs, which is INCOMPLETE, not a statement about the subject's behavior.
"""

from __future__ import annotations

import _bridge as bridge


def main() -> int:
    bridge.start()
    handled = bridge.brief_and_draft()
    bridge.artifact("briefing", bridge.briefing_text(handled))
    bridge.complete(f"Prepared {len(handled)} draft responses.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
