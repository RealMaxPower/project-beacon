from __future__ import annotations

"""The commands used while writing a scenario: `init`, `validate`, `prove`."""

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from beacon.builtins import resolve_scenario
from beacon.falsifiability import Subject, discover_subjects
from beacon.falsifiability import prove as prove_scenario
from beacon.models import Scenario
from beacon.scaffold import scaffold
from beacon.services import import_service_module, is_service


def init(args: argparse.Namespace) -> int:
    created = scaffold(
        args.scenario_id, args.dir, service=args.service, force=args.force
    )
    for path in created:
        print(f"created  {path}")
    directory = args.dir / args.scenario_id
    print()
    print(f"Next: {directory / 'README.md'} has the two commands to run.")
    print("The second one is meant to fail. That is how you know it grades.")
    return 0


def validate(path: Path, service_modules: Sequence[str] = ()) -> int:
    for module in service_modules:
        import_service_module(module)
    scenario = Scenario.load(resolve_scenario(path))
    print(
        json.dumps(
            {
                "valid": True,
                "id": scenario.id,
                "name": scenario.name,
                "assertions": len(scenario.assertions),
                # A fixture is only a service if something is registered under
                # that name. Calling a plain data fixture a service implies the
                # subject gets tools it will never be offered.
                "services": sorted(
                    name for name in scenario.fixtures if is_service(name)
                ),
                "data_fixtures": sorted(
                    name for name in scenario.fixtures if not is_service(name)
                ),
            },
            indent=2,
        )
    )
    return 0


def prove(args: argparse.Namespace) -> int:
    """
    Run the subjects and report what each assertion's falsifiability rests on.

    Exit 1 rather than 2 when something is unproven: it is a finding about the
    scenario, not an error in the invocation, and `run` already draws that line
    the same way so this is usable as a CI gate without special-casing.
    """
    for module in args.service_module:
        import_service_module(module)
    scenario_path = resolve_scenario(args.scenario)
    scenario = Scenario.load(scenario_path)

    if args.subject:
        subjects = [Subject.from_script(Path(p), args.timeout) for p in args.subject]
    else:
        subjects = discover_subjects(scenario_path, args.timeout)

    if not subjects:
        # Saying "0 unproven" here would be the vacuous pass this command exists
        # to find, so it is an error rather than a green result.
        print(
            f"error: no subjects found for {scenario.id}. Looked in "
            f"{scenario_path.parent / 'subjects'}; pass --subject to name them.",
            file=sys.stderr,
        )
        return 2

    report = prove_scenario(scenario, subjects)
    if args.json:
        print(
            json.dumps(
                {
                    "scenario": report.scenario_id,
                    "subjects": report.subjects_run,
                    "ok": report.ok,
                    "broken_by": {k: v for k, v in sorted(report.by_assertion.items())},
                    "exempt": report.exempt,
                    "unfalsifiable": report.impossible,
                    "unproven": list(report.unproven),
                },
                indent=2,
            )
        )
    else:
        print(report.summary())
    return 0 if report.ok else 1
