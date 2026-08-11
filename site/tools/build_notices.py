#!/usr/bin/env python3
"""
Write `public/THIRD-PARTY-NOTICES.txt` from the packages that ship in the build.

    python3 site/tools/build_notices.py
    python3 site/tools/build_notices.py --check

React and React-DOM are MIT, and MIT permits redistribution only if the
copyright notice and the permission notice travel with the copies. A bundled
React is a substantial portion of the software by any reading, and the built
`dist/assets/*.js` carried neither: the minifier dropped the `@license` blocks
and nothing put them back. Naming a licence is not shipping it — the same gap
the fonts had, in a place nobody thinks to look because the dependency arrived
through a lockfile rather than a download.

Generated rather than written by hand, and from the installed packages rather
than from the lockfile's `license` field, because that field is a string
somebody typed. The licence text this reproduces is the one on disk in the
package that is actually being redistributed.

The set is derived from `package-lock.json`: every entry not marked `dev` is
something the browser receives.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
LOCK = SITE / "package-lock.json"
MODULES = SITE / "node_modules"
OUT = SITE / "public" / "THIRD-PARTY-NOTICES.txt"

PREAMBLE = """\
Third-party notices for the Project Beacon website
==================================================

The pages under this origin are built with the packages listed below, and
their compiled code is served to your browser. Each licence permits that only
if its notice travels with the copy, so this file is that notice.

Project Beacon itself is Apache 2.0 — see the LICENSE file in the repository.
The typefaces are covered separately by /fonts/OFL.txt, because the Open Font
Licence has its own attachment requirement.

Written by `site/tools/build_notices.py` from the installed packages. Do not
edit by hand.

"""

# Filenames a package uses for the text a redistributor has to carry.
CANDIDATES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "COPYING")


def shipped() -> list[str]:
    """Every package the browser receives, newest resolution wins."""
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    names = set()
    for path, meta in lock.get("packages", {}).items():
        if not path.startswith("node_modules/") or meta.get("dev"):
            continue
        names.add(path.split("node_modules/")[-1])
    return sorted(names)


def licence_text(name: str) -> str:
    directory = MODULES / name
    for candidate in CANDIDATES:
        path = directory / candidate
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()
    raise SystemExit(
        f"{name} ships no licence file. It is redistributed to every visitor, "
        f"so its terms cannot be guessed — find them and add the filename to "
        f"CANDIDATES, or stop shipping it."
    )


def render() -> str:
    parts = [PREAMBLE]
    for name in shipped():
        version = json.loads(
            (MODULES / name / "package.json").read_text(encoding="utf-8")
        )["version"]
        parts.append("-" * 70)
        parts.append(f"{name} {version}")
        parts.append("-" * 70)
        parts.append("")
        parts.append(licence_text(name))
        parts.append("")
    return "\n".join(parts) + "\n"


def main(argv: list[str]) -> int:
    if not MODULES.is_dir():
        raise SystemExit("node_modules is absent; run `npm install` first.")
    rendered = render()
    if "--check" in argv:
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        if current != rendered:
            print(
                f"{OUT.relative_to(SITE)} is out of date; run "
                f"`python3 site/tools/build_notices.py`.",
                file=sys.stderr,
            )
            return 1
        print(f"{OUT.relative_to(SITE)} is current.")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(rendered, encoding="utf-8")
    print(f"{len(shipped())} notices written to {OUT.relative_to(SITE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
