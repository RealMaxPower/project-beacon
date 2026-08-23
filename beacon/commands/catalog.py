from __future__ import annotations

"""The commands that list what ships: `scenarios`, `taxonomy`, `adapters`."""

import argparse
import json
import sys

from beacon.builtins import builtin_names, builtin_root
from beacon.cliadapters import adapter_rows
from beacon.models import Scenario


def scenarios() -> int:
    root = builtin_root()
    names = builtin_names()
    if not names:
        print(
            "No built-in scenarios found in this installation.", file=sys.stderr
        )
        return 2
    print(f"Built-in scenarios ({root}):")
    for name in names:
        scenario = Scenario.load(root / name / "scenario.json")
        print(f"  {name:32} {scenario.name}")
    print()
    print("Run one by name, with no path:  beacon run inbox-briefing")
    return 0


def taxonomy(args: argparse.Namespace) -> int:
    from beacon.taxonomy import (
        coverage_report,
        load_shipped,
        load_taxonomy,
        taxonomy_path,
    )

    root = builtin_root()
    if root is None:
        print("No built-in scenarios found in this installation.", file=sys.stderr)
        return 2
    taxonomy = load_taxonomy()
    report = coverage_report(load_shipped(root), taxonomy)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    if args.uncovered:
        if not report["uncovered_core"]:
            print("Every gradeable cell is covered.")
            return 0
        known = taxonomy.by_id()
        print(f"Gradeable cells no scenario covers yet ({len(report['uncovered_core'])}):")
        for cell_id in report["uncovered_core"]:
            print(f"\n  {cell_id}")
            print(f"    {known[cell_id].title}")
            print(f"    {known[cell_id].why}")
        return 0

    print(f"Failure taxonomy {report['taxonomy_version']} ({taxonomy_path()})")
    print()
    print(
        f"  {report['covered_core']} of {report['cells_core']} cells this build can "
        f"grade ({report['percent_core']}%)"
    )
    print(
        f"  {report['covered_total']} of {report['cells_total']} cells overall "
        f"({report['percent_total']}%)"
    )
    print(f"  {report['out_of_scope']} candidates considered and rejected")
    print()
    print(f"  {'Family':16} {'Covered':>9} {'Gradeable':>10} {'Total':>7}")
    for family, row in report["by_family"].items():
        print(
            f"  {family:16} {row['covered']:>9} {row['core']:>10} {row['total']:>7}"
        )
    print()
    print("A cell counts as covered when a scenario binds it to a named assertion")
    print("and a subject is observed making that assertion fail. Covered means")
    print("probed once, not solved.")
    print()
    print("The cells nobody has built yet:  beacon taxonomy --uncovered")
    return 0


def adapters() -> int:
    print(json.dumps(adapter_rows(), indent=2))
    return 0
