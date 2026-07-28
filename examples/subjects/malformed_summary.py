#!/usr/bin/env python3
"""
Ignores every injection, and still gets the output shape wrong.

Included because the interesting schema failure is not a subject that returns
a string where an object was asked for — that is obvious from any glance at
the output. It is one whose answer looks right: correct top-level keys, right
types, plausible content, and four small departures spread through nested
structures.

The reason `conforms_to` reports every violation rather than the first: fixing
these one run at a time would take four runs against a live agent.
"""

from __future__ import annotations

import _bridge as bridge
import _injection_bridge as work


def main() -> int:
    bridge.start()
    documents = work.project_documents()
    summary = work.summary_of(documents)

    summary["documents"][0]["point"] = "ok"          # below minLength 10
    summary["documents"][1].pop("path")              # required property missing
    summary["themes"] = [1, "vendor contract"]       # wrong item type
    summary["confidence"] = 0.8                      # additionalProperties false

    bridge.artifact("summary", summary)
    bridge.complete("Summarised the project documents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
