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

#: Absolute forms of a link into this repository, which the README must use.
SELF_LINK_PREFIXES = (
    "https://github.com/RealMaxPower/project-beacon/blob/main/",
    "https://github.com/RealMaxPower/project-beacon/tree/main/",
)

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100,
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
                # A link into this repository is checkable whether it is
                # written relative or absolute. README.md had to go absolute —
                # it is also the package's PyPI description, where a relative
                # path resolves against pypi.org and reaches nothing — and
                # that alone dropped this check below its own floor, which is
                # what the floor is for. Mapping the absolute form back to a
                # path keeps the coverage instead of trading it away.
                inside = None
                for prefix in SELF_LINK_PREFIXES:
                    if target.startswith(prefix):
                        inside = target[len(prefix):]
                        break
                if inside is not None:
                    checked += 1
                    resolved = (ROOT / inside.split("#")[0].rstrip("/")).resolve()
                    if not resolved.exists():
                        broken.append(f"{path.relative_to(ROOT)}: [{label[:40]}]({target})")
                    continue
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

        This used to assert only that the substring "2/12" appeared *somewhere*
        in the file, and it passed for months while a table four screens lower
        printed `12 / 12` and `4 / 12` for the same two runs — inverting the
        story the section told, in the guide a new user is pointed at. Every
        fraction is checked now, against the assertion it names.
        """
        guide = (ROOT / "docs" / "agent-builders.md").read_text(encoding="utf-8")
        recorded = {
            path.name.split(".")[0]: json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((ROOT / "baselines").glob("*.json"))
        }
        fractions = {
            f"{round(rate * bundle['runs'])}/{bundle['runs']}"
            for bundle in recorded.values()
            for rate in bundle.get("assertion_pass_rates", {}).values()
        }
        self.assertTrue(fractions, "no baseline rates were parsed; the guard is decorative")

        quoted = re.findall(r"(\d+)\s*/\s*(\d+)", guide)
        self.assertTrue(quoted, "the guide no longer quotes a measured rate")
        for numerator, denominator in quoted:
            with self.subTest(fraction=f"{numerator}/{denominator}"):
                self.assertIn(
                    f"{numerator}/{denominator}",
                    fractions,
                    f"the guide quotes {numerator}/{denominator}, which no "
                    f"committed baseline records. Recorded: {sorted(fractions)}",
                )


class DocumentedInventoryTests(unittest.TestCase):
    """
    Lists and counts in prose, checked against the registries they describe.

    Every one of these was wrong when the guard was written, and none of them
    was catchable by the checks that existed. `docs/architecture.md` said
    "Beacon ships `mail` and `files`" with six registered; `docs/windows.md`
    told a Windows user to expect "nine passing assertions" and "40/40 verdicts
    correct" against ten and 415; the builder guide documented eight assertion
    types out of eighteen.

    The link and path guards above pass on all of it, because a stale sentence
    names no broken path. Nothing reads a count.
    """

    DOCS = sorted((ROOT / "docs").glob("*.md"))

    def _tracked_prose(self) -> list[Path]:
        return [*self.DOCS, README, SUBJECTS_README, ROOT / "CONTRIBUTING.md"]

    def test_every_shipped_service_is_named_where_services_are_enumerated(self) -> None:
        """
        A sentence naming two or more services is claiming to list them.

        Not a ban on mentioning one service — `files` alone in an example is
        fine. The failure mode is the half-list that reads as complete, which
        is what "Beacon ships `mail` and `files`" became the day `web` landed.
        """
        from beacon.services import registered_services

        services = sorted(registered_services())
        # Sentences, not lines: a list of six service names wraps, and a
        # line-based check reported the last one as missing because it had
        # been pushed onto the next line by the margin.
        for path in self._tracked_prose():
            text = " ".join(path.read_text(encoding="utf-8").split())
            for sentence in re.split(r"(?<=[.!?])\s+", text):
                named = [name for name in services if f"`{name}`" in sentence]
                if len(named) < 2:
                    continue
                with self.subTest(file=path.relative_to(ROOT), sentence=sentence[:60]):
                    self.assertEqual(
                        sorted(named),
                        services,
                        f"{path.name} enumerates services but names "
                        f"{sorted(named)} of {services}: {sentence[:120]}",
                    )

    def test_no_document_states_a_stale_verdict_tally(self) -> None:
        """`N/N verdicts correct` is the suite's own output, so it is checkable."""
        expected = len(json.loads(MANIFEST.read_text(encoding="utf-8"))["subjects"])
        for path in self._tracked_prose():
            text = path.read_text(encoding="utf-8")
            for quoted in re.findall(r"(\d+)\s*/\s*(\d+)\s+verdicts correct", text):
                with self.subTest(file=path.relative_to(ROOT), quoted=quoted):
                    self.assertEqual(
                        [int(quoted[0]), int(quoted[1])],
                        [expected, expected],
                        f"{path.name} states {quoted[0]}/{quoted[1]} verdicts "
                        f"against {expected} subjects",
                    )

    def test_the_readme_layout_names_every_core_module(self) -> None:
        """
        A module missing from the layout block is invisible to the path guard,
        which only checks that named paths exist. `beacon/assertions.py` was
        added by a commit that moved eighteen assertion handlers into it, and
        `models.py` — which CONTRIBUTING calls a published contract — had never
        been listed at all.
        """
        listed = README.read_text(encoding="utf-8")
        modules = sorted(
            path.name
            for path in (ROOT / "beacon").glob("*.py")
            if path.name not in {"__init__.py", "__main__.py"}
        )
        missing = [name for name in modules if name not in listed]
        self.assertEqual(
            missing,
            [],
            f"the repository layout does not mention {missing}",
        )

    #: Assertion types the builder guide may leave out, and why. Empty on
    #: purpose: if a type is worth registering it is worth a row, and an
    #: exemption should have to be argued for in writing here rather than by
    #: quietly not mentioning it.
    UNDOCUMENTED_ASSERTIONS: dict[str, str] = {}

    def test_the_builder_guide_names_every_assertion_type(self) -> None:
        """
        The guide documented eight of eighteen, and the ten it omitted were
        not the obscure ones: `equals` is the most-used type in the shipped
        scenarios, and `matches_path` is the only one that compares what an
        agent *said* against what the state records.
        """
        from beacon.assertions import REGISTRY

        guide = (ROOT / "docs" / "agent-builders.md").read_text(encoding="utf-8")
        missing = sorted(
            name
            for name in REGISTRY
            if f"`{name}`" not in guide and name not in self.UNDOCUMENTED_ASSERTIONS
        )
        self.assertEqual(
            missing,
            [],
            f"docs/agent-builders.md does not mention {missing}. Add a row, or "
            f"add the name to UNDOCUMENTED_ASSERTIONS with a reason.",
        )

    def test_the_evidence_version_is_stated_correctly_wherever_it_appears(self) -> None:
        from beacon.models import EVIDENCE_VERSION

        for path in self._tracked_prose():
            text = path.read_text(encoding="utf-8")
            for quoted in re.findall(r"`evidence_version`[^.\n]*?`(\d+\.\d+)`", text):
                with self.subTest(file=path.relative_to(ROOT), quoted=quoted):
                    self.assertEqual(quoted, EVIDENCE_VERSION)


class VerificationTranscriptTests(unittest.TestCase):
    """
    `docs/verifying-a-checkout.md` prints expected output, and expected output
    carries version numbers.

    A reader runs the command beside it and compares. If the number in the
    comment is a release behind, either they conclude the checkout is wrong or
    they learn to ignore the comments — and a transcript nobody compares
    against is decoration in a document whose whole genre is comparison.

    Both numbers here are computed from the thing that prints them, so a
    version bump that forgets this file fails rather than ships. The badge in
    the README taught this lesson at the cost of a permanently wrong project
    page for 0.1.1.
    """

    DOC = ROOT / "docs" / "verifying-a-checkout.md"

    #: `# 0.1.1` annotating a command that asks for the version.
    ANNOTATED = re.compile(
        r"(?:--version|__version__)[^\n#]*#\s*([0-9]+\.[0-9]+\.[0-9]+)"
    )
    PRINTED_TAXONOMY = re.compile(r"Failure taxonomy ([0-9]+\.[0-9]+\.[0-9]+)")

    def test_the_printed_package_version_is_the_current_one(self) -> None:
        from beacon import __version__

        found = self.ANNOTATED.findall(self.DOC.read_text(encoding="utf-8"))
        self.assertGreater(
            len(found), 0, "this guard found no annotated version command"
        )
        self.assertEqual(sorted(set(found)), [__version__])

    def test_the_printed_test_count_is_a_band_and_the_band_is_true(self) -> None:
        """
        The figure in §1 was typed, and it drifted.

        This class already pins the two *versions* in that transcript, computed
        from the things that print them, explicitly so a version bump that
        forgets the file fails rather than ships. The test count in the same
        block was pinned by nothing, and read `Ran 871 tests` while the suite
        reported 896 — in the one document whose §4 exists to demonstrate that
        published figures are computed rather than typed, and whose whole
        premise is that a disagreeing number means a bug.

        A band rather than the exact number, deliberately. Pinning the count
        exactly would fail the suite on every commit that adds a test, which is
        the churn the README rejected when it chose "Over 800" — so this uses
        the same shape and the same tolerance as the README's own guard.
        """
        stated = re.search(r"Ran ([\d,]+)\+ tests", self.DOC.read_text(encoding="utf-8"))
        self.assertIsNotNone(
            stated, "§1 no longer states a test count as a band; see this test's docstring"
        )
        claimed = int(stated.group(1).replace(",", ""))

        actual = (
            unittest.TestLoader()
            .discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
            .countTestCases()
        )
        self.assertGreater(actual, 0, "no tests were discovered; this guard would pass on anything")
        self.assertLessEqual(
            claimed, actual, f"the document promises {claimed}+ tests and there are {actual}"
        )
        self.assertGreaterEqual(
            claimed,
            actual * 0.7,
            f"the document says {claimed}+ and there are {actual}; it understates by over a third",
        )

    def test_the_model_ladder_claim_matches_the_committed_baselines(self) -> None:
        """
        §7 says how many runs closed its own verification gap. Count them.

        The paragraph it replaced said "nobody has verified this section from
        outside with an actual model behind it", and that stopped being true
        without the document noticing — the same drift as the test count and the
        skip count before it, in the same file, for the third time.

        This one *is* computable, because the evidence was committed:
        `--repeat 5` against five models is twenty-five runs, and each baseline
        records its own run count. So the sentence is pinned to the files rather
        than to whoever last edited it.
        """
        text = self.DOC.read_text(encoding="utf-8")
        stated = re.search(r"\*\*No PASS in ([a-z-]+|\d+) runs\.\*\*", text)
        self.assertIsNotNone(stated, "§7 no longer states the ladder result")

        words = {"twenty-five": 25, "twenty five": 25}
        claimed = words.get(stated.group(1), None)
        if claimed is None:
            claimed = int(stated.group(1))

        ladder = sorted((ROOT / "baselines").glob("inbox-briefing.ollama-*.json"))
        self.assertGreater(len(ladder), 0, "no ladder baselines to count")
        actual = sum(
            json.loads(path.read_text(encoding="utf-8"))["runs"] for path in ladder
        )
        self.assertEqual(
            claimed,
            actual,
            f"§7 claims {claimed} runs; the committed baselines record {actual}",
        )
        # The other half of the claim: none of them passed.
        for path in ladder:
            with self.subTest(baseline=path.name):
                self.assertNotIn(
                    "PASS",
                    json.loads(path.read_text(encoding="utf-8"))["verdicts"],
                    "§7 says no run passed, and this baseline records one that did",
                )

    def test_the_transcript_types_no_skip_count(self) -> None:
        """
        The same disease as the count above, caught a second time.

        §1 said ten checks skip on a fresh clone and the suite reports
        `OK (skipped=10)`. That was measured, and true, at 0.1.2. Twelve site
        guards landed afterwards and a fresh clone reports 22 — so a reader
        following this document's own instruction, that a disagreeing number
        means a bug, would file one against a suite that is working.

        There is no band to use here. A test count only grows, so `870+` stays
        honest; a skip count moves whenever a guard is added, removed, or
        changes which directory it depends on, and nothing in the tree computes
        it — the number is only knowable by running the suite in a checkout that
        has never built the site, which is not a state this suite can observe
        from inside a checkout that has.

        So the figure is not restated more carefully, it is removed, and this
        keeps it out. The reason it exists is worth more to a reader than the
        arithmetic: the checks that read the built site skip, and §6 turns them
        on.
        """
        text = self.DOC.read_text(encoding="utf-8")
        # Guard the guard: if the transcript block ever stops mentioning skips,
        # this test is watching a document that no longer says anything.
        self.assertIn(
            "skip", text, "§1 no longer mentions skipping at all; see this test's docstring"
        )

        typed = re.findall(r"skipped\s*=\s*(\d+)|(\b(?:[Tt]en|[Tw]welve|\d+)\b) checks", text)
        self.assertEqual(
            [next(g for g in match if g) for match in typed],
            [],
            "§1 types a skip count again; nothing computes it, so it will drift "
            "the way `skipped=10` did between 0.1.2 and the twelve guards after it",
        )

    def test_the_printed_taxonomy_version_is_the_current_one(self) -> None:
        published = json.loads(
            (ROOT / "taxonomy" / "failure-modes.json").read_text(encoding="utf-8")
        )["taxonomy_version"]
        found = self.PRINTED_TAXONOMY.findall(self.DOC.read_text(encoding="utf-8"))
        self.assertGreater(
            len(found), 0, "this guard found no printed taxonomy version"
        )
        self.assertEqual(sorted(set(found)), [published])


class SelfIdentificationTests(unittest.TestCase):
    """
    When Beacon introduces itself to a peer, it must say which Beacon it is.

    MCP's `serverInfo`/`clientInfo` version is the implementation version, and
    it is where a host's logs and a user's bug report get their version from.
    Three sites had it typed as a literal, written at 0.1.0 and never bumped —
    so a 0.1.1 install introduced itself as 0.1.0 to every host it spoke to.
    That is the badge defect again, in the field where being wrong costs a
    misdirected diagnosis rather than a misprinted page.

    Scoped to the package's own name on purpose. `beacon-echo-fixture` and
    `beacon-reference-mcp-host` are separate components with their own
    identities, and pinning them here would assert something untrue about them.
    """

    #: A `{"name": "project-beacon", "version": …}` pair, either order, as it
    #: appears in the source rather than at runtime.
    IDENTITY = re.compile(
        r'"name":\s*"project-beacon",\s*"version":\s*([^,}\s]+)', re.S
    )

    def test_every_place_beacon_names_itself_reports_the_real_version(self) -> None:
        from beacon import __version__

        found: list[tuple[str, str]] = []
        for path in sorted((ROOT / "beacon").rglob("*.py")):
            for value in self.IDENTITY.findall(path.read_text(encoding="utf-8")):
                found.append((path.name, value))

        self.assertGreater(
            len(found), 0, "this guard found no self-identification to check"
        )
        literal = [(name, value) for name, value in found if value != "__version__"]
        self.assertEqual(
            literal,
            [],
            "these announce a version that cannot follow the package; use "
            f"`__version__` (currently {__version__}): {literal}",
        )


if __name__ == "__main__":
    unittest.main()
