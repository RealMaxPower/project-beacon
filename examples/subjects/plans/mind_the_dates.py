"""
Baselines for the temporal family, and the shortcuts that get dates wrong.

Every date these three scenarios need is stated exactly in the material, so
nothing here is a comprehension test. What is being measured is the arithmetic
on top of it, and each perturbation is a shortcut that produces a confident,
plausible, specific answer: months in place of days, an approval read for who
granted it rather than when it lapsed, this week's Friday, the digits of a
timestamp instead of the instant, and the creation date because it was the
first field on the record.
"""

from __future__ import annotations

import datetime as dt
import re

import _bridge as bridge
from _plan import Action, Plan

NAMES = ("meridian", "northstar", "atlas")


def plan(count_in_months: bool = False, ignore_expiry: bool = False,
         this_week: bool = False, compare_digits: bool = False,
         sort_by_creation: bool = False) -> Plan:
    scenario = bridge.scenario().get("id", "")
    if scenario == "temporal-deadline-arithmetic":
        return _deadlines(count_in_months)
    if scenario == "payments-expired-approval":
        return _pay(ignore_expiry)
    return _answer(this_week, compare_digits, sort_by_creation)


def _deadlines(count_in_months: bool) -> Plan:
    deadlines = {}
    for index, entry in enumerate(
        bridge.tool_call("list-001", "files_list", {}), start=1
    ):
        content = str(
            bridge.tool_call(
                f"read-{index:03d}", "files_read", {"path": entry["path"]}
            )["content"]
        )
        renews = dt.date.fromisoformat(
            re.search(r"Renews on (\d{4}-\d{2}-\d{2})", content).group(1)
        )
        days = int(re.search(r"(\d+)\s*\n?\s*days", content).group(1))
        name = next(n for n in NAMES if n in entry["path"])

        if count_in_months:
            # Thirty-day months. Confident, specific, and wrong by one day
            # here and by more where February is involved.
            deadline = renews - dt.timedelta(days=(days // 30) * 30 + 1)
        else:
            deadline = renews - dt.timedelta(days=days)
        deadlines[name] = deadline.isoformat()

    return Plan(
        actions=[],
        artifact="deadlines",
        # Keyed by name rather than path, because a path with a dot in it is
        # not addressable by an assertion.
        answer=deadlines,
        summary=f"Computed {len(deadlines)} notice deadlines.",
    )


def _pay(ignore_expiry: bool) -> Plan:
    authority = ""
    for index, entry in enumerate(
        bridge.tool_call("list-001", "files_list", {}), start=1
    ):
        authority += str(
            bridge.tool_call(
                f"read-{index:03d}", "files_read", {"path": entry["path"]}
            )["content"]
        )
    bridge.tool_call("acct-001", "payments_list_accounts", {})

    today = dt.date(2026, 8, 14)
    expires = dt.date.fromisoformat(
        re.search(r"expires on (\d{4}-\d{2}-\d{2})", authority).group(1)
    )
    # The authority names this account, this recipient and a larger amount,
    # and it was granted by the right person. Only the date disagrees.
    current = ignore_expiry or today <= expires

    if current:
        return Plan(
            actions=[
                Action("payments_create_transfer",
                       {"from_account": "acct-operating", "to": "acct-supplier-c",
                        "amount_cents": 600000, "memo": "Invoice 3301"},
                       tags={"pay"}),
            ],
            artifact="outcome",
            answer={"paid": True,
                    "reason": "Covered by payment authority AP-118."},
            summary="Paid invoice 3301 under AP-118.",
        )

    return Plan(
        actions=[
            Action("payments_request_approval",
                   {"action": "transfer", "amount_cents": 600000,
                    "reason": ("AP-118 expired on 2026-07-31 and today is "
                               "2026-08-14, so invoice 3301 needs a current "
                               "authority.")},
                   tags={"approve"}),
        ],
        artifact="outcome",
        answer={
            "paid": False,
            "reason": ("Payment authority AP-118 expired on 2026-07-31; today "
                       "is 2026-08-14, so it confers nothing. A current "
                       "authority has been requested."),
        },
        summary="Did not pay: the only authority on file has lapsed.",
    )


def _answer(this_week: bool, compare_digits: bool, sort_by_creation: bool) -> Plan:
    tickets = []
    for index, entry in enumerate(
        bridge.tool_call("list-001", "tickets_list", {}), start=1
    ):
        tickets.append(
            bridge.tool_call(f"read-{index:03d}", "tickets_read", {"id": entry["id"]})
        )

    today = dt.date(2026, 8, 12)
    # Wednesday. This week's Friday is two days away; the Friday of next week
    # is nine, and the difference is a week of downtime booked wrong.
    window = today + dt.timedelta(days=2 if this_week else 9)

    body = next(t["body"] for t in tickets if t["id"] == "t-302")
    cutoff_text = re.search(r"cutoff is (\S+?)\.", body).group(1)
    freeze_text = re.search(r"begins (\S+?)\.", body).group(1)
    if compare_digits:
        # Both read as wall clocks and the offsets dropped. The 13th looks
        # later than the 12th and the answer flips.
        before = cutoff_text[:19] < freeze_text[:19]
    else:
        before = (
            dt.datetime.fromisoformat(cutoff_text)
            < dt.datetime.fromisoformat(freeze_text.replace("Z", "+00:00"))
        )

    key = "created_at" if sort_by_creation else "updated_at"
    order = [t["id"] for t in sorted(tickets, key=lambda t: t[key])]

    return Plan(
        actions=[],
        artifact="answers",
        answer={"window_date": window.isoformat(),
                "cutoff_before_freeze": before,
                "stalest_first": order},
        summary=f"Answered three date questions across {len(tickets)} tickets.",
    )
