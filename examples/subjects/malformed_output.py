#!/usr/bin/env python3
"""
Control: writes non-protocol text to standard output.

A stray `print`, a progress bar, or a framework banner on stdout corrupts the
channel. `docs/protocol-contracts.md` reserves stdout for protocol messages, so
this is a contract violation and must resolve to INCOMPLETE rather than being
silently skipped.
"""

from __future__ import annotations

import sys

import _bridge as bridge


def main() -> int:
    bridge.start()
    sys.stdout.write("Loading model weights... done\n")
    sys.stdout.flush()
    bridge.complete("Never reached in practice.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
