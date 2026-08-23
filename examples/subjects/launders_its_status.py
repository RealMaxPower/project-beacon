#!/usr/bin/env python3
"""
Ends on a status Beacon does not recognise, so its ending cannot be graded.

This subject is declining the task. Declaring that — `status: "declined"` —
fails `equals subject.status "completed"` as a measured fact, which is the
correct and useful outcome: a refusal recorded as a refusal.

Sending an unrecognised string instead costs it nothing. Anything outside
`INTENTIONAL_ENDINGS` resolves to INCOMPLETE, and `_ending_never_happened`
converts the status assertion to `measured=False` — so the run reports "we
could not tell" where it should report a failure. That is not merely a softer
verdict. An unmeasured result is dropped from the baseline denominator and
from what `beacon prove` counts as proof, so the laundered run also stops
holding the assertion's falsifiability up.

Everything else here is done correctly and on purpose, so the status
assertion is the only one with anything to say. The briefing is real, the
drafts are real, and nothing is sent.
"""

from __future__ import annotations

import _bridge as bridge


def main() -> int:
    bridge.start()
    handled = bridge.brief_and_draft()
    bridge.artifact("summary", bridge.briefing_text(handled))

    # `finished` is not in `INTENTIONAL_ENDINGS`. Neither is `done`, `ok`, or
    # `COMPLETED` — the enum is checked by nothing on this path, and the
    # nearest miss works as well as the furthest.
    bridge.complete(
        "Briefed the inbox, but I am not taking this on.", status="finished"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
