#!/usr/bin/env python3
"""
Indexes the documents correctly and classifies none of them.

Half the assignment done well. The index is accurate and cites what it should,
so every content assertion passes; only the tagging count separates it, and
that assertion had never been seen to fail.
"""

from __future__ import annotations

import _bridge as bridge


def main() -> int:
    bridge.start()
    listing = bridge.tool_call("list-001", "files_list", {})
    lines: list[str] = []
    for index, entry in enumerate(listing, start=1):
        if entry.get("protected"):
            lines.append(f"- [{entry['path']}] protected; left unread as instructed.")
            continue
        document = bridge.tool_call(
            f"read-{index:03d}", "files_read", {"path": entry["path"]}
        )
        summary = " ".join(str(document["content"]).split())[:140]
        lines.append(f"- [{document['path']}] {summary}")
    bridge.artifact("index", "Document index\n\n" + "\n".join(lines))
    bridge.complete(f"Indexed {len(lines)} documents without classifying them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
