"""
A baseline whose answer has the same structure twice, and one whose does not.

Nothing here can be nondeterministic — a scripted subject run twice on the
same input produces the same bytes, which is the property the rest of this
suite depends on. So `let_the_run_show` does the next most honest thing: it
lets something outside the task decide its output shape. The run identifier is
not part of the question and is not the same in both passes, and a subject
whose structure depends on it is the scripted stand-in for the sampling
variance a real agent has. The failure it models is not "the agent knew it was
pass two" — it is that nothing pinned the shape down, so anything at all was
free to move it.
"""

from __future__ import annotations

import _bridge as bridge
from _plan import Plan

STATUS = {"approved": "approved", "on hold": "on hold"}


def plan(let_the_run_show: bool = False, always_omit: bool = False) -> Plan:
    documents = []
    for index, entry in enumerate(
        bridge.tool_call("list-001", "files_list", {}), start=1
    ):
        content = str(
            bridge.tool_call(
                f"read-{index:03d}", "files_read", {"path": entry["path"]}
            )["content"]
        )
        status = "on hold" if "on hold" in content else "approved"
        blockers = (
            ["the pending security review"] if "Blocked by" in content else []
        )
        documents.append(
            {"path": entry["path"], "status": status, "blockers": blockers}
        )

    # Deterministic per pass and different between them: the second pass's run
    # identifier carries a suffix the first one does not. If the runner ever
    # stops appending it, this subject stops breaking its assertion and the
    # falsifiability test says so — loudly, rather than by quietly passing.
    unstable = len(str(bridge.start_run_id())) % 2 == 0

    if always_omit or (let_the_run_show and unstable):
        # The field that vanishes when it is empty. Every value is right and
        # the consumer written against the other pass reads a missing key.
        documents = [
            {k: v for k, v in document.items() if k != "blockers" or v}
            for document in documents
        ]

    return Plan(
        actions=[],
        artifact="result",
        answer={"documents": documents},
        summary=f"Reported {len(documents)} documents.",
    )
