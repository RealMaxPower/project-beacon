from __future__ import annotations

import json
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

    #: Every upstream, with the year its own notice carries.
    #:
    #: Written out rather than globbed because the point is that each notice is
    #: reproduced *verbatim*: a year that drifts is a notice that is no longer
    #: the upstream's. Inter's is `(c) 2016`, not `2016`, and that difference is
    #: exactly the kind this check exists to hold.
    NOTICES = (
        ("Copyright 2020", "The Space Grotesk Project Authors"),
        ("Copyright 2020", "The JetBrains Mono Project Authors"),
        ("Copyright 2020", "The Archivo Project Authors"),
        ("Copyright (c) 2016", "The Inter Project Authors"),
        ("Copyright 2021", "The Azeret Project Authors"),
    )

    def test_every_upstream_copyright_notice_is_reproduced(self) -> None:
        licence = self.LICENCE.read_text(encoding="utf-8")
        for prefix, holder in self.NOTICES:
            with self.subTest(holder=holder):
                self.assertIn(f"{prefix} {holder}", licence)

    def test_no_redistributed_family_reserves_its_name(self) -> None:
        """
        A Reserved Font Name and a Modified Version cannot coexist.

        This file states that subsetting makes these Modified Versions, and
        clause 3 forbids one from using a reserved name. IBM Plex — which the
        second design originally specified — declares `Reserved Font Name
        "Plex"`, so it cannot ship here; Inter replaced it for that reason and
        no other. The check is on the stylesheets rather than the licence,
        because the family name in an `@font-face` is where the reserved name
        would actually be used.
        """
        reserved = ("Plex", "Source Sans", "Source Serif", "Source Code", "PT Sans", "PT Serif")
        for path in sorted(SITE.rglob("fonts*.css")):
            declared = re.findall(r"font-family:\s*'([^']+)'", path.read_text(encoding="utf-8"))
            for family in declared:
                for name in reserved:
                    with self.subTest(file=path.name, family=family):
                        self.assertNotIn(
                            name,
                            family,
                            f"{family} carries the reserved name {name!r}",
                        )

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
        # Every generated stylesheet, not just the first design's — the
        # preamble is shared, so a second one that drifted would be invisible
        # to a check that only ever read one file.
        written = sorted(SITE.rglob("fonts*.css"))
        self.assertGreaterEqual(len(written), 1, "no generated stylesheets found")
        for path in written:
            with self.subTest(file=path.relative_to(ROOT)):
                css = path.read_text(encoding="utf-8")
                self.assertTrue(css.startswith(header.group(1).rstrip("\n")))


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class BundledPackageLicenceTests(unittest.TestCase):
    """
    The compiled site redistributes its dependencies to every visitor, and
    their licences require the notice to travel with the copy.

    Nothing published it. `dist/assets/*.js` carried no copyright line and no
    permission text, because the minifier discards comments and no step put
    them back — the same failure the fonts had, reached through a lockfile
    rather than a download, which is why it survived longer. A dependency
    nobody chose to vendor is still one being redistributed.
    """

    def test_the_bundled_packages_ship_their_notices(self) -> None:
        """
        React is MIT, every visitor receives a compiled copy of it, and MIT
        permits that only with its notice attached. The built assets carried
        none: the minifier dropped the `@license` blocks and nothing replaced
        them. The same omission the fonts had, arrived at through a lockfile
        instead of a download, which is why it went unnoticed for longer.

        Derived from the lockfile rather than a list, so a new runtime
        dependency is covered the moment it is installed.
        """
        notices = SITE / "public" / "THIRD-PARTY-NOTICES.txt"
        self.assertTrue(notices.is_file(), "nothing publishes the bundled licences")
        text = notices.read_text(encoding="utf-8")

        lock = json.loads((SITE / "package-lock.json").read_text(encoding="utf-8"))
        shipped = {
            path.split("node_modules/")[-1]
            for path, meta in lock.get("packages", {}).items()
            if path.startswith("node_modules/") and not meta.get("dev")
        }
        self.assertTrue(shipped, "the lockfile lists nothing that reaches a browser")
        for name in sorted(shipped):
            with self.subTest(package=name):
                self.assertIn(name, text)

    def test_the_notices_carry_licence_text_rather_than_a_licence_name(self) -> None:
        """
        "MIT" is the name of a licence, not the notice it requires. The file
        has to contain the permission text a redistributor is obliged to pass
        on, and the copyright line naming who holds it.
        """
        text = (SITE / "public" / "THIRD-PARTY-NOTICES.txt").read_text(encoding="utf-8")
        self.assertIn("Permission is hereby granted, free of charge", text)
        self.assertIn("Copyright (c) Meta Platforms", text)

    def test_the_site_points_at_both_notice_files(self) -> None:
        """
        Two licences with an attachment requirement, and a page that names
        neither is a page that satisfies neither in practice — the files would
        sit on the origin with nothing linking them.
        """
        legal = (SITE / "src" / "screens" / "marketing" / "Legal.tsx").read_text(
            encoding="utf-8"
        )
        for target in ("/THIRD-PARTY-NOTICES.txt", "/fonts/OFL.txt"):
            with self.subTest(target=target):
                self.assertIn(target, legal)

if __name__ == "__main__":
    unittest.main()
