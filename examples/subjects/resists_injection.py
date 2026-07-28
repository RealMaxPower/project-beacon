#!/usr/bin/env python3
"""
Control: does the assignment and ignores the instructions inside the files.

It reads both project documents — including the injected blocks — summarises
them, and does none of what they demand. Nothing here is clever; treating
retrieved text as data is simply the correct behaviour, and this subject
exists to show the scenario does not punish it.
"""

from __future__ import annotations

import _bridge as bridge
import _injection_bridge as work


def main() -> int:
    bridge.start()
    documents = work.project_documents()
    bridge.artifact("summary", work.summary_of(documents))
    bridge.complete("Summarised the project documents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
