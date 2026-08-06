#!/usr/bin/env python3
"""
Download the two typefaces into `site/public/fonts/`, so the site serves them.

    python3 site/tools/fetch_fonts.py

The mocks link the Google Fonts CDN. A site whose argument is that evidence
should be checkable should not hand every visitor's IP address to a third party
to render its own headings, and the CDN link is render-blocking besides. Both
families are SIL Open Font Licence 1.1, so serving them ourselves is allowed
and is the smaller behaviour.

The files this writes are committed. Rerun it only to change weights.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
FONTS = ROOT / "site" / "public" / "fonts"
CSS = ROOT / "site" / "src" / "fonts.css"

# The API returns woff2 only when it believes the caller is a browser that
# supports it; with the default urllib agent it serves truetype, which is
# roughly twice the size.
CHROME = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
API = (
    "https://fonts.googleapis.com/css2"
    "?family=Space+Grotesk:wght@400;500"
    "&family=JetBrains+Mono:wght@400;500"
    "&display=swap"
)

# Subsets worth carrying for an English site: latin, plus latin-ext so an
# accented name in a scenario fixture or a contributor's byline still renders.
KEEP = frozenset({"latin", "latin-ext"})

# Google does not label the subsets in the CSS it returns, so they are
# identified by the codepoints each block declares. U+0100 opens Latin
# Extended-A; a block that mentions it is latin-ext, one that does not and
# covers ASCII is latin, and everything else is a script this site drops.
SUBSET_MARKERS = (("latin-ext", "U+0100"), ("latin", "U+0000"))


def _subset_name(ranges: str) -> str:
    for name, marker in SUBSET_MARKERS:
        if marker in ranges:
            return name
    return "other"


HEADER = """/*
 * Written by `site/tools/fetch_fonts.py`. Do not edit by hand.
 *
 * Space Grotesk and JetBrains Mono, both SIL Open Font Licence 1.1, served
 * from this origin rather than a font CDN. See the script for why.
 *
 * Licence: public/fonts/OFL.txt, which ships beside the files. The OFL
 * allows redistribution only with the licence attached, so it is a file in
 * the repository rather than this sentence.
 */
"""


def _get(url: str) -> bytes:
    """
    Fetch with curl rather than urllib.

    urllib validates against Python's own certificate store, which on a
    python.org macOS build is empty until `Install Certificates.command` is
    run. This is a developer-only asset fetcher that runs perhaps twice in the
    life of the project; depending on the operating system's trust store via
    curl is more portable than asking every contributor to fix theirs, and
    beacon itself still has no runtime dependency either way.
    """
    if shutil.which("curl") is None:
        raise SystemExit("curl is required to fetch fonts.")
    result = subprocess.run(
        ["curl", "-sSfL", "-A", CHROME, url],
        capture_output=True,
        check=True,
    )
    return result.stdout


def main() -> int:
    FONTS.mkdir(parents=True, exist_ok=True)
    css = _get(API).decode("utf-8")

    blocks = re.findall(r"@font-face \{(.*?)\}", css, re.S)
    if not blocks:
        print("The font API returned no @font-face blocks.", file=sys.stderr)
        return 1

    # Both families are variable fonts, so every weight of one family and
    # subset resolves to the same file. Collected by URL, they collapse from
    # eight downloads to four, each declared over a weight range instead of a
    # single weight — the browser instances the axis itself.
    faces: dict[str, dict[str, Any]] = {}
    for block in blocks:
        family = re.search(r"font-family: '([^']+)'", block)
        weight = re.search(r"font-weight: (\d+)", block)
        url = re.search(r"url\((https://[^)]+\.woff2)\)", block)
        ranges = re.search(r"unicode-range: ([^;]+);", block)
        if not (family and weight and url):
            continue

        # The API returns one face per unicode-range subset — latin, latin-ext,
        # cyrillic, vietnamese and so on. Only latin and latin-ext are kept:
        # the rest are weight the site would download and never render. Keeping
        # the subsets separate is what makes that safe, because a browser only
        # fetches a face whose unicode-range it actually needs.
        subset = _subset_name(ranges.group(1) if ranges else "")
        if subset not in KEEP:
            continue

        face = faces.setdefault(
            url.group(1),
            {
                "family": family.group(1),
                "subset": subset,
                "ranges": ranges.group(1) if ranges else "",
                "weights": set(),
            },
        )
        face["weights"].add(int(weight.group(1)))

    out: list[str] = [HEADER]
    for url_value, face in faces.items():
        stem = face["family"].replace(" ", "-").lower()
        name = f"{stem}-{face['subset']}.woff2"
        (FONTS / name).write_bytes(_get(url_value))

        weights = sorted(face["weights"])
        declared = (
            str(weights[0])
            if len(weights) == 1
            else f"{weights[0]} {weights[-1]}"
        )
        out.append(
            "@font-face {\n"
            f"  font-family: '{face['family']}';\n"
            "  font-style: normal;\n"
            f"  font-weight: {declared};\n"
            "  font-display: swap;\n"
            f"  src: url('/fonts/{name}') format('woff2');\n"
            + (f"  unicode-range: {face['ranges']};\n" if face["ranges"] else "")
            + "}\n"
        )
        print(f"  {name:<38} weight {declared}")

    CSS.write_text("\n".join(out), encoding="utf-8")
    print(f"\n{len(out) - 1} faces written to {CSS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
