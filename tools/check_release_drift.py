#!/usr/bin/env python3
"""
Report when the version this repository declares is not a version anyone has.

`pyproject.toml` announcing `0.3.0` is a claim. The evidence for it is a
`v0.3.0` tag and a `0.3.0` on PyPI, and nothing in the suite could compare the
three: the version is bumped in one commit and tagged in another, so a test that
demanded a tag would be red through every release, and the suite is hermetic so
it cannot ask PyPI at all.

0.3.0 is why this exists. It was cut on 2026-08-23 — version bumped, changelog
written, `docs/production-readiness.md` updated to say "Released on PyPI" — and
the tag was never pushed. For a week the package announced a version that
existed nowhere, the readiness ledger asserted a release that had not happened,
and every test passed, because none of them was looking. It was found by
someone asking whether a release was needed, which is not a mechanism.

The gap between cutting a release and publishing one is legitimate; it is only
ever supposed to be minutes. So this does not forbid the gap, it bounds it:
after `GRACE_DAYS` the claim has outlived any honest explanation.

Run by `.github/workflows/release-drift.yml` on a schedule. The comparison
itself is a pure function so the suite can exercise it without a network or a
particular day.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
PYPI_JSON = "https://pypi.org/pypi/project-beacon/json"

GRACE_DAYS = 3
"""
How long a declared version may go untagged before it counts as drift.

A release takes minutes, so this is generous rather than tight. It exists
because the window between the bump commit and the tag is real and legitimate,
and a check that fired inside it would be red on every release — which is how a
check gets ignored, and then how it gets deleted.
"""


def drift(
    version: str,
    tags: set[str],
    published: set[str],
    declared_days_ago: float,
    grace_days: float = GRACE_DAYS,
) -> list[str]:
    """
    What is wrong with the claim that `version` is this project's version.

    Pure, and takes every fact as an argument, so the suite can ask it about a
    version tagged yesterday or a PyPI that cannot be reached without either
    being true today. The three links are checked in order, because a missing
    tag explains a missing release and reporting both would be one finding
    twice.
    """
    if f"v{version}" not in tags:
        if declared_days_ago < grace_days:
            return []
        return [
            f"pyproject.toml declares {version}, and no v{version} tag exists. "
            f"It has said so for {declared_days_ago:.0f} days. A version is cut "
            f"and then tagged, so a gap here is normal for minutes and means a "
            f"release stalled after {grace_days:.0f} days — which is how 0.3.0 "
            f"sat unpublished for a week while the readiness ledger said "
            f"otherwise."
        ]
    if not published:
        # Distinguished from "published, but not this version": an unreachable
        # index is not evidence that nothing shipped, and reporting it as
        # though it were would be the same overstatement in a new place.
        return ["could not read the published versions from PyPI, so the tag was not checked against it"]
    if version not in published:
        return [
            f"v{version} is tagged but {version} is not on PyPI. The tag "
            f"triggers the release workflow and the publish job then waits for "
            f"a reviewer, so a tag without a release usually means that "
            f"deployment was never approved."
        ]
    return []


def declared_version(text: str) -> str:
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    if not match:
        raise SystemExit("could not read version from pyproject.toml")
    return match.group(1)


def _tags() -> set[str]:
    out = subprocess.run(
        ("git", "tag", "-l"), cwd=ROOT, capture_output=True, text=True, check=False
    )
    return {line.strip() for line in out.stdout.splitlines() if line.strip()}


def _declared_days_ago(version: str) -> float:
    """
    Days since the commit that set this version string.

    `-S` finds the commit that introduced the line rather than the last commit
    to touch the file, so ordinary edits elsewhere in `pyproject.toml` do not
    reset the clock.
    """
    out = subprocess.run(
        ("git", "log", "-1", "--format=%ct", "-S", f'version = "{version}"', "--", "pyproject.toml"),
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    stamp = out.stdout.strip()
    if not stamp:
        return 0.0
    return (time.time() - float(stamp)) / 86400.0


def _published() -> set[str]:
    # `_ssl_context` rather than the default, and reused rather than rewritten:
    # a python.org install on macOS ships an empty CA directory until
    # `Install Certificates.command` is run, so this fails with
    # CERTIFICATE_VERIFY_FAILED on a developer machine while working in CI —
    # a check that only breaks where somebody would run it by hand. The
    # protocol clients hit this first and already fall back to certifi.
    sys.path.insert(0, str(ROOT))
    from beacon.protocols.mcp_http import _ssl_context

    try:
        with urllib.request.urlopen(
            PYPI_JSON, timeout=20, context=_ssl_context()
        ) as response:
            return set(json.loads(response.read().decode("utf-8"))["releases"])
    except Exception:
        # Reported by `drift` as "could not read", never as "nothing shipped".
        return set()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Skip PyPI and check the version against the tags only.",
    )
    args = parser.parse_args()

    version = declared_version(PYPROJECT.read_text(encoding="utf-8"))
    problems = drift(
        version,
        _tags(),
        {version} if args.offline else _published(),
        _declared_days_ago(version),
    )
    if not problems:
        print(f"{version} is declared, tagged and published.")
        return 0
    for problem in problems:
        print(f"drift: {problem}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
