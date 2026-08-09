#!/usr/bin/env python3
"""
Completes the scenario correctly, then hangs past the timeout.

The MCP sibling of `subjects/slow_teardown.py`, and it exists for the same
reason: closing an HTTP connection pool, joining a non-daemon thread, or
flushing an SDK client all take time, and all of it happens after the work is
finished and `beacon_submit` has already been sent.

Beacon terminates the host, records that it did, and still reports the verdict
the submission earned. It used to report INCOMPLETE — "we did not measure
this" — for work it had already graded and held the artifact for.

    python3 -m beacon run scenarios/inbox-briefing/scenario.json \
      --adapter mcp-host \
      --command "python3 examples/mcp_host_slow_teardown.py" \
      --timeout 5

The work itself is `mcp_host_agent`'s, imported rather than copied so this
file is only the teardown behaviour. Beacon launches the host by absolute
path, which puts this directory on `sys.path`.
"""

from __future__ import annotations

import time
import urllib.error

import mcp_host_agent as host

# Longer than any timeout a test would give it, so the harness is always the
# thing that ends this process.
TEARDOWN_SECONDS = 600


def main() -> int:
    code = host.main()
    if code != 0:
        return code
    time.sleep(TEARDOWN_SECONDS)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as exc:  # pragma: no cover - transport failure
        print(f"could not reach Beacon's MCP server: {exc}")
        raise SystemExit(1)
