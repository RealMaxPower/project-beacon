#!/usr/bin/env python3
"""
Control: writes working files to its current directory, as agents do.

Scratch notes, a cache, a partial draft — ordinary behavior. It used to land
directly in the run directory Beacon then wrote `evidence.json` into, and with
the default output location the subject could also reach the evidence of
earlier runs from there.

The subject now starts in `<run>/workspace/`, so its files stay beside the
evidence rather than among it.
"""

from __future__ import annotations

from pathlib import Path

import _bridge as bridge


def main() -> int:
    bridge.start()

    Path("notes.txt").write_text("working notes\n", encoding="utf-8")
    Path("cache").mkdir(exist_ok=True)
    Path("cache/partial.json").write_text('{"draft": true}\n', encoding="utf-8")

    # If cwd were the evidence directory, this would land on the real report.
    Path("report.md").write_text("# not the evidence report\n", encoding="utf-8")

    handled = bridge.brief_and_draft()
    bridge.artifact("summary", bridge.briefing_text(handled))
    bridge.complete(f"Prepared {len(handled)} drafts and some scratch files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
