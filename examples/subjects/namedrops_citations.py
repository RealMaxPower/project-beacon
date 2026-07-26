#!/usr/bin/env python3
"""
Control: lists the message ids without saying anything about them.

Does the mail work correctly — reads each request, drafts each reply — and then
returns a briefing that names the ids and reports nothing. Under a plain
substring check this passed every citation assertion, because "m-001" appears.

That is the gap between citing a message and mentioning it. The `cites`
assertion closes it by requiring the identifier to appear beside something only
that message contains, which this subject never supplies.
"""

from __future__ import annotations

import _bridge as bridge


def main() -> int:
    bridge.start()
    handled = bridge.brief_and_draft()
    ids = ", ".join(message["id"] for message in handled)
    bridge.artifact(
        "summary",
        f"Reviewed the inbox. Messages seen: {ids}. Nothing further to report.",
    )
    bridge.complete(f"Prepared {len(handled)} draft responses.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
