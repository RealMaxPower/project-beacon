from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
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

    # Only claims about *this* suite. `beacon init` writes two subjects and the
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
