#!/usr/bin/env python3
"""
Run every adversarial subject against the starter scenario and report which
verdicts Beacon gets wrong.

    python3 examples/subjects/run_suite.py
    python3 examples/subjects/run_suite.py --keep-evidence .beacon/suite

Exits non-zero if any subject's verdict has drifted from what the manifest
records, so this doubles as a regression check while the known defects are
being closed.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from beacon.adapters import JSONLCommandAdapter  # noqa: E402
from beacon.models import Scenario  # noqa: E402
from beacon.runner import run_scenario  # noqa: E402

MANIFEST = ROOT / "examples" / "subjects" / "manifest.json"
DEFAULT_TIMEOUT = 15.0


def _run(case: dict[str, Any], scenario_path: Path, output_dir: str) -> Any:
    adapter = JSONLCommandAdapter(
        [sys.executable, str(ROOT / case["script"])],
        timeout_seconds=float(case.get("timeout_seconds", DEFAULT_TIMEOUT)),
    )
    return run_scenario(
        Scenario.load(scenario_path),
        adapter,
        output_dir=output_dir,
        run_id=case["id"],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep-evidence",
        type=Path,
        help="Write run directories here instead of a temporary directory.",
    )
    args = parser.parse_args(argv)

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    scenario_path = ROOT / manifest["scenario"]
    subjects = manifest["subjects"]

    if args.keep_evidence:
        args.keep_evidence.mkdir(parents=True, exist_ok=True)
        output_dir: Any = args.keep_evidence
        context = None
    else:
        context = tempfile.TemporaryDirectory()
        output_dir = context.name

    print(f"{'subject':<30} {'verdict':<11} {'should be':<11} status")
    print("-" * 78)

    wrong: list[dict[str, Any]] = []
    drifted: list[str] = []
    try:
        for case in subjects:
            outcome = _run(case, scenario_path, str(output_dir))
            actual = outcome.evidence.result
            if actual != case["currently"]:
                drifted.append(
                    f"{case['id']}: manifest says {case['currently']}, got {actual}"
                )
            if actual == case["should_be"]:
                status = "ok"
            else:
                status = "WRONG"
                wrong.append(case)
            print(
                f"{case['id']:<30} {actual:<11} {case['should_be']:<11} {status}"
            )
    finally:
        if context is not None:
            context.cleanup()

    print()
    print(f"{len(subjects) - len(wrong)}/{len(subjects)} verdicts correct.")

    if wrong:
        print("\nOpen defects:")
        for case in wrong:
            print(f"  {case['id']}")
            print(f"    {case['defect']}")

    if drifted:
        print("\nManifest drift - behavior changed since it was recorded:")
        for line in drifted:
            print(f"  {line}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
