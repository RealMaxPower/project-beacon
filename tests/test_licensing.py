from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LICENSE = ROOT / "LICENSE"
PYPROJECT = ROOT / "pyproject.toml"
SITE = ROOT / "site"


class ProjectLicenceTests(unittest.TestCase):
    """
    The licence file has to say who is licensing the work.

    A full Apache 2.0 pasted from a template ends at END OF TERMS AND
    CONDITIONS, and the appendix carrying the copyright line is the part that
    goes missing — which is exactly what happened here. The file then granted
    terms for eleven months without naming a holder to grant them, while
    `pyproject.toml` declared `license = "Apache-2.0"` and every reader
    reasonably assumed the two agreed.
    """

    def test_the_licence_carries_its_appendix(self) -> None:
        self.assertIn(
            "APPENDIX: How to apply the Apache License",
            LICENSE.read_text(encoding="utf-8"),
        )

    def test_the_licence_names_a_holder_and_a_year(self) -> None:
        self.assertRegex(LICENSE.read_text(encoding="utf-8"), r"(?m)^\s*Copyright \d{4} \S.*$")

    def test_the_template_placeholders_were_filled_in(self) -> None:
        """
        The failure this guards is not an empty file, it is a plausible one.
        `Copyright [yyyy] [name of copyright owner]` satisfies a reader
        skimming for a copyright line and names nobody.
        """
        text = LICENSE.read_text(encoding="utf-8")
        for placeholder in ("[yyyy]", "[name of copyright owner]"):
            with self.subTest(placeholder=placeholder):
                self.assertNotIn(placeholder, text)

    def test_the_declared_licence_and_the_file_agree(self) -> None:
        """Metadata and the file it points at, pinned to each other."""
        self.assertIn('license = "Apache-2.0"', PYPROJECT.read_text(encoding="utf-8"))
        self.assertIn("Apache License", LICENSE.read_text(encoding="utf-8"))

    def test_the_holder_matches_the_declared_authors(self) -> None:
        """
        Two places name the same party, so they are pinned together rather
        than left to drift into naming different ones.
        """
        authors = re.search(
            r'authors\s*=\s*\[\s*\{\s*name\s*=\s*"([^"]+)"',
            PYPROJECT.read_text(encoding="utf-8"),
        )
        self.assertIsNotNone(authors, "the authors field moved; repoint this guard")
        self.assertIn(f"Copyright 2026 {authors.group(1)}", LICENSE.read_text(encoding="utf-8"))


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class FontLicenceTests(unittest.TestCase):
    """
    The four woff2 files are a redistribution, and the Open Font Licence
    permits one only with the licence attached.

    This is the one licence breach this repository could commit by accident.
    The files arrive from a script rather than a person, no import statement
    mentions them, and `fonts.css` said "both SIL Open Font Licence 1.1" in a
    comment that reads as compliance while the licence itself had never been
    committed. Naming a licence is not shipping it.
    """

    FONTS = SITE / "public" / "fonts"
    LICENCE = FONTS / "OFL.txt"

    def test_there_are_fonts_to_check(self) -> None:
        """A passing check that examined no fonts proves nothing."""
        self.assertTrue(sorted(self.FONTS.glob("*.woff2")))

    def test_the_licence_ships_beside_them(self) -> None:
        self.assertIn(
            "SIL OPEN FONT LICENSE Version 1.1",
            self.LICENCE.read_text(encoding="utf-8"),
        )

    def test_every_redistributed_file_is_covered_by_name(self) -> None:
        """
        A licence naming one family while the directory holds two is the
        failure mode that survives a glance, so each file is listed.
        """
        licence = self.LICENCE.read_text(encoding="utf-8")
        for path in sorted(self.FONTS.glob("*.woff2")):
            with self.subTest(font=path.name):
                self.assertIn(path.name, licence)

    def test_both_upstream_copyright_notices_are_reproduced(self) -> None:
        licence = self.LICENCE.read_text(encoding="utf-8")
        for holder in ("The Space Grotesk Project Authors", "The JetBrains Mono Project Authors"):
            with self.subTest(holder=holder):
                self.assertIn(f"Copyright 2020 {holder}", licence)

    def test_the_generator_and_the_stylesheet_agree(self) -> None:
        """
        `fetch_fonts.py` rewrites `fonts.css` wholesale from its HEADER
        constant, so a licence pointer added to the stylesheet by hand is
        deleted the next time anyone reruns the script. The two copies are
        pinned to each other rather than trusted to stay in step.
        """
        source = (SITE / "tools" / "fetch_fonts.py").read_text(encoding="utf-8")
        header = re.search(r'HEADER = """(.*?)"""', source, re.S)
        self.assertIsNotNone(header, "the header constant moved; repoint this guard")
        self.assertIn("OFL.txt", header.group(1))
        css = (SITE / "src" / "fonts.css").read_text(encoding="utf-8")
        self.assertTrue(css.startswith(header.group(1).rstrip("\n")))


if __name__ == "__main__":
    unittest.main()
