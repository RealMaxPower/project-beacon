#!/usr/bin/env python3
"""
Lists every document path and says nothing about what is in them.

The shape of a real failure: an agent that enumerates rather than reads, and
produces an index that looks complete. Paths are all present, so any check
counting entries passes. The citation assertions are what notice that no
distinctive detail from inside a document ever appears.
"""

from __future__ import annotations

import _bridge as bridge


def main() -> int:
    bridge.start()
    listing = bridge.tool_call("list-001", "files_list", {})
    lines = []
    for index, entry in enumerate(listing, start=1):
        path = entry["path"]
        if not entry.get("protected"):
            bridge.tool_call(
                f"tag-{index:03d}",
                "files_tag",
                {"path": path, "tag": "reviewed"},
            )
        lines.append(f"- [{path}] on file.")
    bridge.artifact("index", "Document index\n\n" + "\n".join(lines))
    bridge.complete(f"Listed {len(lines)} documents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
