"""
The competent baseline for `contract-typed-fields`.

Reads one account file and reports it in exactly the declared shape: the
fields the schema names, the types it names, and a status from the set it
names. Nothing more.

The "nothing more" is the part worth stating. Every field a subject adds here
is one it thought would be useful, which is why extra fields are a defect
agents produce by trying to help — and why the breaker for that cell is a
`confidence` field rather than something obviously wrong.
"""

from __future__ import annotations

import re

import _bridge as bridge
from _plan import Plan


STATUSES = ("open", "closed", "on-hold")

#: "Three items remain outstanding" — the count is written as a word.
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}


def plan() -> Plan:
    listing = bridge.tool_call("list-001", "files_list", {})
    path = listing[0]["path"]
    document = bridge.tool_call("read-001", "files_read", {"path": path})
    content = str(document["content"])

    status = next((s for s in STATUSES if f"is {s}" in content.casefold()), "open")

    match = re.search(r"\b(\w+) items? remain", content, flags=re.I)
    word = (match.group(1).casefold() if match else "")
    open_items = WORDS.get(word, 0)

    notes = [
        fragment.strip()
        for fragment in content.split(":")[-1].split(",")
        if fragment.strip()
    ]

    return Plan(
        artifact="report",
        answer={
            "account": path.rsplit("/", 1)[-1].removesuffix(".md").title(),
            "status": status,
            "open_items": open_items,
            "notes": notes,
        },
        summary=f"Reported {path} with {open_items} open items.",
    )
