#!/usr/bin/env python3
"""Resolves the low-priority tickets and leaves the urgent one alone."""

from __future__ import annotations

import _pack_bridge as bridge


def main() -> int:
    bridge.start()
    closed = bridge.triage()
    bridge.finish(f"Closed {len(closed)} low-priority tickets.", closed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
