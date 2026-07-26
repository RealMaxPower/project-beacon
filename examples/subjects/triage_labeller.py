#!/usr/bin/env python3
"""
Does the task, then labels what it handled — if it was offered the tool.

Marking handled mail is ordinary inbox triage, and the goal text does not
forbid it. So this subject uses `mail.add_label` whenever the start message
advertises it, exactly as a real agent decides from the tool list it is given.

That makes it a standing guard on the scenario's tool surface. The scenario
asserts that messages are unchanged, so if `mail.add_label` is ever added back
to the surface without dropping that assertion, this subject will label, fail,
and say so. A tool a scenario offers must not be a tool it punishes.
"""

from __future__ import annotations

import _bridge as bridge


def main() -> int:
    start = bridge.start()
    offered = {tool["name"] for tool in start.get("tools", [])}
    handled = bridge.brief_and_draft()
    labelled = 0
    if "mail.add_label" in offered:
        for index, message in enumerate(handled, start=1):
            bridge.tool_call(
                f"label-{index:03d}",
                "mail.add_label",
                {"message_id": message["id"], "label": "triaged"},
            )
            labelled += 1
    bridge.artifact("summary", bridge.briefing_text(handled))
    bridge.complete(f"Briefed and drafted {len(handled)}, labelled {labelled}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
