#!/usr/bin/env python3
"""
Re-grade stored evidence bundles against the current scenario.

    python3 conformance/regrade.py .beacon/agent-probe --report regraded.md

The first pass of the hosted-agent probe scored several agents as fabricating
when they had in fact returned an empty result set — the check looked for
prose like "not found", and a retrieval tool says the same thing as
`{"count": 0, "items": []}`. Fixing the assertion meant re-grading, and
re-grading meant either calling forty strangers' services again or reading
the answers already on disk.

That is what an evidence bundle is for. Every artifact the subject returned
was recorded, so the verdict can be recomputed offline, for free, against a
corrected scenario. Anything that changed verdict is a case the original
assessment got wrong.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from beacon.evaluation import evaluate_all, resolve_result  # noqa: E402
from beacon.models import EVIDENCE_VERSION, Event, Scenario  # noqa: E402

ASK_TOOL = re.compile(r"(^|_)(ask|answer|explain|chat|question)", re.I)


def regrade(bundle: Path, scenario: Scenario) -> dict[str, Any]:
    evidence = json.loads(bundle.read_text(encoding="utf-8"))
    root = {
        "before": evidence["state"].get("before", {}),
        "after": evidence["state"].get("after", {}),
        "artifacts": evidence.get("artifacts", {}),
        "subject": evidence["subject"].get("execution", {}),
        "fixtures": scenario.fixtures,
        "usage": evidence.get("usage", {}),
        "repeat": evidence.get("repeat", []),
    }
    events = [
        Event(
            sequence=item.get("sequence", 0),
            timestamp=item.get("timestamp", ""),
            kind=item.get("kind", ""),
            target=item.get("target", ""),
            payload=item.get("payload", {}),
        )
        for item in evidence.get("events", [])
    ]
    results = evaluate_all(scenario.assertions, root, events)
    verdict = resolve_result(root["subject"].get("status", "unknown"), results)
    tool = evidence["subject"].get("tool", "")
    return {
        "name": evidence["subject"].get("name", bundle.parent.name),
        "tool": tool,
        "kind": "ask" if ASK_TOOL.search(tool) else "search",
        "was": evidence["result"],
        # Which rule produced each verdict. `was` was decided by whatever
        # evaluator wrote the bundle; `now` is decided by this one. They are
        # not the same claim when the rules differ between them — evidence 0.3
        # grades `input_required` and `declined` as endings the subject chose,
        # where 0.2 resolved both to INCOMPLETE — so a re-grade that reported a
        # bare before/after would be asserting a change of behaviour where
        # there was only a change of rule.
        "was_rule": evidence.get("evidence_version", "unknown"),
        "now_rule": EVIDENCE_VERSION,
        "now": verdict,
        "answer_chars": len(str(evidence.get("artifacts", {}).get("answer", ""))),
        "failed": [r.id for r in results if not r.passed],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument(
        "--scenario",
        type=Path,
        default=ROOT / "scenarios" / "fabrication-probe" / "scenario.json",
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    scenario = Scenario.load(args.scenario)
    bundles = sorted(args.directory.glob("*/evidence.json"))
    records = [regrade(bundle, scenario) for bundle in bundles]
    changed = [r for r in records if r["was"] != r["now"]]

    print(f"Re-graded {len(records)} stored bundles against {args.scenario.name}\n")
    for record in records:
        arrow = f"{record['was']} -> {record['now']}" if record in changed else record["now"]
        flag = "CHANGED" if record in changed else ""
        print(
            f"  {record['kind']:<7} {record['name'][:34]:<34} "
            f"{record['tool'][:26]:<26} {arrow:<22} {flag}"
        )

    graded = [r for r in records if r["now"] in {"PASS", "FAIL"}]
    ask = [r for r in graded if r["kind"] == "ask"]
    search = [r for r in graded if r["kind"] == "search"]
    print(f"\n  {len(changed)} verdicts changed after correcting the check")
    print(f"  graded: {len(graded)}   ask-style: {len(ask)}   search-style: {len(search)}")
    for label, group in (("ask", ask), ("search", search)):
        counts = Counter(r["now"] for r in group)
        print(f"    {label:<7} {dict(counts)}")

    if args.report:
        lines = [
            "# Hosted agent fabrication probe (re-graded)",
            "",
            f"{len(records)} agents, graded offline from stored evidence bundles.",
            "",
            "The first pass scored an empty result set as fabrication, because it "
            "looked for prose like \"not found\" and a retrieval tool answers "
            f"`{{\"count\": 0}}`. Correcting that changed **{len(changed)}** "
            "verdicts. Bundles made the fix free — no agent was called twice.",
            "",
            "## Ask-style tools (a model writes prose)",
            "",
            "These assert things in sentences, so a non-empty answer about an "
            "invented identifier is a hallucination.",
            "",
            "| Agent | Tool | Verdict | Answer |",
            "|---|---|---|---|",
        ]
        for r in sorted(ask, key=lambda r: -r["answer_chars"]):
            lines.append(
                f"| {r['name']} | `{r['tool']}` | {r['now']} | {r['answer_chars']} chars |"
            )
        lines += [
            "",
            "## Search-style tools (retrieval)",
            "",
            "A non-empty result here is *not* necessarily fabrication — a "
            "semantic search returning nearest neighbours for a nonsense query "
            "is doing its job badly, not lying. Reported separately for that "
            "reason.",
            "",
            "| Agent | Tool | Verdict | Answer |",
            "|---|---|---|---|",
        ]
        for r in sorted(search, key=lambda r: -r["answer_chars"]):
            lines.append(
                f"| {r['name']} | `{r['tool']}` | {r['now']} | {r['answer_chars']} chars |"
            )
        args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nWrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
