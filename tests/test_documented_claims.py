from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
README = ROOT / "README.md"
SUBJECTS_README = ROOT / "examples" / "subjects" / "README.md"
MANIFEST = ROOT / "examples" / "subjects" / "manifest.json"
A2A_SURVEY = ROOT / "conformance" / "a2a-survey.md"

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
}


def _as_number(token: str) -> int:
    """
    Read "40", "forty", or "twenty-one" as an integer.

    Unknown spellings raise rather than being skipped: a counting claim this
    cannot read is one it cannot check, and silently passing it would make the
    whole guard decorative.
    """
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    total = 0
    for part in token.split("-"):
        if part not in NUMBER_WORDS:
            raise ValueError(f"cannot read {token!r} as a number")
        total += NUMBER_WORDS[part]
    return total


class SubjectCountTests(unittest.TestCase):
    """
    The prose count of adversarial subjects must match the manifest.

    `run_suite.py` fails when the manifest drifts from the subjects on disk,
    and `test_adversarial_subjects.py` fails when a recorded verdict drifts
    from reality. Nothing watched the *prose*, and the prose drifted: the
    README said "twenty-one subjects" ten lines above its own "40/40 verdicts
    correct", having grown by nineteen subjects without the sentence moving.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.expected = len(json.loads(MANIFEST.read_text(encoding="utf-8"))["subjects"])

    def test_the_manifest_has_subjects_to_count(self) -> None:
        self.assertGreater(self.expected, 0)

    # Only claims about *this* suite. `project-beacon init` writes two subjects and the
    # subjects README has a section about a different pair; both are correct
    # and neither is a count of the adversarial suite.
    CLAIMS = (
        re.compile(r"([A-Za-z-]+|\d+)\s+subjects that behave", re.IGNORECASE),
        re.compile(r"all\s+([A-Za-z-]+|\d+)\s+subjects", re.IGNORECASE),
    )

    def test_every_documented_subject_count_matches_the_manifest(self) -> None:
        found: list[tuple[str, str, int]] = []
        for path in (README, SUBJECTS_README):
            label = str(path.relative_to(ROOT))
            text = " ".join(path.read_text(encoding="utf-8").split())
            for pattern in self.CLAIMS:
                for match in pattern.finditer(text):
                    found.append((label, match.group(0), _as_number(match.group(1))))

        self.assertGreaterEqual(
            len(found), 3, f"the counting claims moved; found only {found}"
        )
        for name, claim, value in found:
            with self.subTest(file=name, claim=claim):
                self.assertEqual(value, self.expected)


class A2ADefectCountTests(unittest.TestCase):
    """
    The README's SDK defect count must match the survey's own table.

    Three documents carried three different numbers for the same finding. The
    survey is the record, so the README is pinned to it rather than the other
    way round.
    """

    @classmethod
    def setUpClass(cls) -> None:
        rows = re.findall(
            r"^\|\s*(Python|JavaScript|Go|Java|\.NET)\s*\|\s*(\d+)\s*\|",
            A2A_SURVEY.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        cls.rows = rows
        cls.sdk_total = sum(int(count) for _, count in rows)

    def test_the_survey_table_was_actually_parsed(self) -> None:
        self.assertEqual(len(self.rows), 5, "expected one row per official SDK")
        self.assertGreater(self.sdk_total, 0)

    def test_the_readme_reports_the_survey_figure(self) -> None:
        # Whitespace-normalised, because prose wraps and a claim must not
        # escape the guard by moving onto the next line.
        text = " ".join(README.read_text(encoding="utf-8").split())
        match = re.search(
            r"which found ([a-z]+|\d+) defects the specification alone did not",
            text,
        )
        self.assertIsNotNone(match, "the README claim moved; repoint this guard")
        self.assertEqual(_as_number(match.group(1)), self.sdk_total)


class StatedCountTests(unittest.TestCase):
    """
    Two counts the README states about itself, and nothing was checking either.

    It said "over 400 tests" while the suite was near 700 — true, and wrong by
    forty percent — in the sentence whose own argument is that a number in
    prose goes stale the week after it is written and nobody notices. And its
    licence section described "the four woff2 files … Space Grotesk and
    JetBrains Mono" when ten files and five families ship. `OFL.txt` named all
    five correctly, so the notice was right and the README's account of it was
    not, which is the more embarrassing direction for a licensing claim.

    Both are derived here rather than read, so neither can drift again.
    """

    README = ROOT / "README.md"

    def test_the_stated_test_count_is_not_far_below_the_real_one(self) -> None:
        """
        A floor, not an equality: the count moves with every commit and a
        README that has to be edited each time will not be. Thirty percent of
        slack, which "over 400" against 698 had long exhausted.
        """
        stated = re.search(
            r"(?:Nearly|Over|More than|Around)\s+([\d,]+)\s+tests", self.README.read_text(encoding="utf-8")
        )
        self.assertIsNotNone(stated, "the README no longer states a test count")
        claimed = int(stated.group(1).replace(",", ""))

        loader = unittest.TestLoader()
        actual = loader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT)).countTestCases()
        self.assertGreater(actual, 0, "no tests were discovered; this guard would pass on anything")
        self.assertLessEqual(
            claimed, actual, f"the README claims {claimed} tests and there are {actual}"
        )
        self.assertGreaterEqual(
            claimed,
            actual * 0.7,
            f"the README says {claimed} and there are {actual}; it understates by more than a third",
        )


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class FontLicenceTests(unittest.TestCase):
    """
    The licence section, against the fonts actually under `site/public/fonts/`.

    Split from the count check above rather than sharing its class, because
    this one reads `site/` and that one must not: the sdist does not carry the
    site, and a guard that skipped the whole class would take the test count
    with it — silent in an unpacked sdist, which is exactly where a stale
    README claim would go unnoticed.
    """

    README = ROOT / "README.md"

    def test_the_licence_section_describes_the_fonts_that_ship(self) -> None:
        fonts = sorted((SITE / "public" / "fonts").glob("*.woff2"))
        self.assertTrue(fonts, "no fonts found; this guard would pass on anything")
        readme = self.README.read_text(encoding="utf-8")

        families = sorted({path.name.split("-latin")[0] for path in fonts})
        self.assertGreaterEqual(len(families), 2, "too few families to be worth checking")

        # Compared with the letters only. A filename cannot carry the
        # capitalisation of a brand — `jetbrains-mono` is JetBrains Mono — and
        # a guard that demanded a spelling derived from the filename would be
        # asserting its own naming convention rather than the licence claim.
        # `assertIn` against the README prints the README, which is not a
        # useful way to learn that one word is missing.
        flat = re.sub(r"[^a-z]", "", readme.lower())
        for family in families:
            wanted = re.sub(r"[^a-z]", "", family.lower())
            with self.subTest(family=family):
                self.assertTrue(
                    wanted in flat,
                    f"{family} ships under site/public/fonts/ and the licence section omits it",
                )

        words = {2: "two", 3: "three", 4: "four", 5: "five", 10: "ten", 12: "twelve"}
        counted = words.get(len(fonts))
        if counted:
            self.assertTrue(
                f"{counted} woff2 files" in readme,
                f"{len(fonts)} woff2 files ship; the README does not say {counted!r}",
            )


class ReferencedPathTests(unittest.TestCase):
    """
    Every repository path the README names must exist.

    This is also the check that would have caught the distribution gap: the
    sdist shipped without `examples/`, so every one of these commands failed
    after a `pip install` while passing in a checkout.
    """

    # Directories the documentation points readers at by path. Each one is a
    # promise that the thing is there when they look.
    REFERENCED = ("examples", "baselines", "scenarios", "schemas", "conformance")

    def test_every_repository_path_in_the_readme_exists(self) -> None:
        text = README.read_text(encoding="utf-8")
        pattern = re.compile(
            r"(?:\./)?(?:" + "|".join(self.REFERENCED) + r")/[A-Za-z0-9_./-]+"
        )
        paths = sorted({m.lstrip("./") for m in pattern.findall(text)})
        self.assertGreater(len(paths), 5, "the README stopped naming paths")
        missing = [path for path in paths if not (ROOT / path).exists()]
        self.assertEqual(missing, [], f"README names paths that do not exist: {missing}")

    def test_no_markdown_link_points_at_a_file_that_is_gone(self) -> None:
        """
        Every markdown link in every tracked file, not just this one.

        The check above reads `README.md` and a list of directory names, which
        is precise and covers one file of thirty-eight. `site/README.md` opened
        with "built from the design system in [`design/`](design/)" for a week
        after that directory was deleted — the first sentence of the site's own
        documentation, pointing at a 404, found by a reader rather than by
        anything here.

        Only markdown link syntax with a repository-relative target, and only
        tracked files. A bare backticked string is as likely to be a protocol
        method (`tools/list`), a MIME type (`application/json`) or a git branch
        (`release/v1`) as a path, and generated output under `dist/` links
        absolute site paths that are correct for a browser and meaningless
        here. A checker that reports those teaches people to skim past it.
        """
        tracked = subprocess.run(
            ("git", "ls-files", "*.md"),
            cwd=ROOT, capture_output=True, text=True, timeout=30, check=False,
        )
        if tracked.returncode != 0:
            self.skipTest("no git repository to list tracked files from")
        files = [ROOT / name for name in tracked.stdout.split()]
        self.assertGreater(len(files), 10, "far fewer markdown files than expected")

        broken, checked = [], 0
        for path in files:
            for label, target in re.findall(
                r"\[([^\]]*)\]\(([^)\s]+)\)", path.read_text(encoding="utf-8")
            ):
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                checked += 1
                resolved = (path.parent / target.split("#")[0].rstrip("/")).resolve()
                if not resolved.exists():
                    broken.append(f"{path.relative_to(ROOT)}: [{label[:40]}]({target})")

        # Thirty-seven today. The floor is only here to catch the regex
        # ceasing to match, which would make this pass on anything.
        self.assertGreater(checked, 25, "almost no relative links were found; has the syntax changed?")
        self.assertEqual(broken, [], "markdown links point at files that do not exist:\n" + "\n".join(broken))

    def test_the_builder_guide_names_paths_that_exist(self) -> None:
        """
        The guide links `baselines/` for the rates it quotes. A link to
        evidence that is not there is worse than quoting no evidence.
        """
        guide = ROOT / "docs" / "agent-builders.md"
        pattern = re.compile(
            r"\.\./(?:" + "|".join(self.REFERENCED) + r")/[A-Za-z0-9_./-]*"
        )
        paths = sorted({m[3:] for m in pattern.findall(guide.read_text(encoding="utf-8"))})
        self.assertGreater(len(paths), 0, "the guide stopped naming paths")
        missing = [path for path in paths if not (ROOT / path).exists()]
        self.assertEqual(missing, [], f"the guide names paths that do not exist: {missing}")

    def test_the_quoted_baseline_rates_match_the_recorded_files(self) -> None:
        """
        The rates in the builder guide are the ones in the committed baselines,
        or the guide is quoting a measurement the repository cannot show.
        """
        guide = " ".join(
            (ROOT / "docs" / "agent-builders.md").read_text(encoding="utf-8").split()
        )
        recorded = json.loads(
            (ROOT / "baselines" / "web-extraction-contract.claude-sonnet-5.json")
            .read_text(encoding="utf-8")
        )
        rate = recorded["assertion_pass_rates"]["result-matches-the-contract"]
        passed = round(rate * recorded["runs"])
        self.assertIn(f"{passed}/{recorded['runs']}", guide)


if __name__ == "__main__":
    unittest.main()
