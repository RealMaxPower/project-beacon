#!/usr/bin/env python3
"""
Reports that there are no matches, having looked at nothing.

The answer is perfectly shaped and, taken alone, indistinguishable from the
correct one: `matches` is empty, `found` is false, every field the contract
requires is present and well typed. `contract-empty-result` asks for exactly
that when the search term appears nowhere — and the term does appear nowhere, so
this subject's *conclusion* is even true.

What is missing is the search. `searched` is 0 because nothing was read, which
is the only trace in the artifact that anything is wrong, and a subject wanting
to hide it would simply write 3.

That is why `the-search-actually-happened` reads the event log rather than the
answer. A tool call is something the subject did and Beacon recorded; a number
in an artifact is something the subject said about itself. This scenario is in
the grounding family, and an empty result asserted rather than established is
the failure that family is named for.
"""

from __future__ import annotations

import _bridge as bridge


def main() -> int:
    bridge.start()
    bridge.artifact(
        "result",
        {"query": "Halloway", "matches": [], "searched": 0, "found": False},
    )
    bridge.complete("No matches for 'Halloway'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
