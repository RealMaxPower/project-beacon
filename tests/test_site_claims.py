from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
SRC = SITE / "src"
GENERATED = SRC / "data" / "generated"
MANIFEST = ROOT / "examples" / "subjects" / "manifest.json"
RUNNER = ROOT / "beacon" / "runner.py"

SOURCE_SUFFIXES = {".ts", ".tsx", ".css", ".html", ".json"}


def _without_comments(source: str) -> str:
    """
    Drop `/* … */`, `//` and `<!-- … -->` comments.

    Several guards below forbid a word appearing in the code. The same word
    usually has to appear in the comment that explains why it is forbidden, and
    a check that cannot tell those apart would punish writing the reason down.

    HTML comments were the gap: an entry document explaining *why* it carries
    no `og:image` was failing the guard that forbids one.
    """
    source = re.sub(r"<!--.*?-->", "", source, flags=re.S)
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"^\s*//.*$", "", source, flags=re.M)


#: Every source tree a marketing surface is built from.
#:
#: `src-b` is the second design, and it is listed here deliberately. A tree
#: that ships to visitors and is not scanned by these guards is a tree where
#: the rules are suggestions — and this file exists because a marketing site is
#: the largest surface of unpinned claims the project has. Adding a third
#: design means adding it here, not inheriting silence.
SOURCE_TREES = (SRC, SITE / "src-b")

#: There is one document now. There were two while a replacement design
#: was reviewed against the one it replaced at a real URL; this stayed a
#: tuple because a second entry is a thing this project does, and the guard
#: that walks it should not have to be rewritten to notice.
ENTRY_POINTS = ("index.html",)


def _site_sources() -> list[Path]:
    """Every file the site is built from. Excludes the design mocks."""
    found = [
        path
        for tree in SOURCE_TREES
        if tree.is_dir()
        for path in sorted(tree.rglob("*"))
        if path.is_file() and path.suffix in SOURCE_SUFFIXES
    ]
    return found + [SITE / name for name in ENTRY_POINTS if (SITE / name).is_file()]


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class GeneratedFixtureTests(unittest.TestCase):
    """
    The playground replays recorded runs. This is what stops them becoming
    authored ones.

    `site/tools/build_fixtures.py` runs real subjects from `examples/subjects/`
    and commits what Beacon wrote. If a subject's behaviour changes, its
    fixture is stale, and a stale fixture is a demo that shows a verdict the
    code no longer produces.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.index = json.loads((GENERATED / "index.json").read_text(encoding="utf-8"))
        cls.subjects = {
            case["id"]: case
            for case in json.loads(MANIFEST.read_text(encoding="utf-8"))["subjects"]
        }

    def test_there_are_fixtures_to_check(self) -> None:
        """A passing suite because the directory was empty proves nothing."""
        self.assertTrue(self.index["fixtures"], "no fixtures recorded")

    def test_every_demo_agent_is_a_real_subject(self) -> None:
        """
        The playground may only demo subjects the adversarial suite records.

        Inventing a demo agent would mean inventing its behaviour, and this
        repository already has forty subjects whose behaviour is recorded.
        """
        for fixture in self.index["fixtures"]:
            subject = fixture["subject"]
            if subject is None:
                continue  # the in-process reference agent, which is not a subject
            with self.subTest(fixture=fixture["key"]):
                self.assertIn(subject, self.subjects)

    def test_recorded_verdicts_match_the_manifest(self) -> None:
        for fixture in self.index["fixtures"]:
            subject = fixture["subject"]
            if subject is None:
                continue
            with self.subTest(fixture=fixture["key"]):
                self.assertEqual(
                    fixture["verdict"],
                    self.subjects[subject]["currently"],
                    "the fixture is stale; rerun site/tools/build_fixtures.py",
                )

    def test_every_fixture_has_its_bundle_on_disk(self) -> None:
        for fixture in self.index["fixtures"]:
            with self.subTest(fixture=fixture["key"]):
                run = GENERATED / fixture["key"]
                self.assertTrue((run / "evidence.json").is_file())
                self.assertTrue((run / "events.json").is_file())

    def test_the_recording_machine_is_not_identifiable(self) -> None:
        """
        No absolute path from whoever generated these may reach the site.

        The command adapter resolves a subject to an absolute path, which on
        the machine that recorded these contained a home directory. It ships to
        a public website; `build_fixtures.py` rewrites it to `<repo>`.
        """
        pattern = re.compile(r"/(?:Users|home)/[^/\"\\s]+/")
        for path in sorted(GENERATED.rglob("*.json")):
            with self.subTest(file=path.relative_to(ROOT)):
                found = pattern.search(path.read_text(encoding="utf-8"))
                self.assertIsNone(
                    found,
                    f"{found.group(0) if found else ''} would be published",
                )


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class ScenarioSourceTests(unittest.TestCase):
    """
    The panel that names a scenario file must be that file.

    Expert mode used to render `scenarios.json` — a projection built for the
    UI, which adds `slug`, `artifact` and `graded_on` and drops
    `schema_version`, `limits` and `metadata` — under the path of the real
    file, tagged REPO. It was 4,636 bytes claiming to be 6,391.

    Nothing caught it: the export was checked against the scenarios, and the
    label was checked against nothing. This checks the bytes.
    """

    def test_every_scenario_ships_byte_identical(self) -> None:
        shipped = GENERATED / "scenarios"
        self.assertTrue(shipped.is_dir(), "the raw scenario files are not shipped")

        originals = sorted((ROOT / "scenarios").glob("*/scenario.json"))
        self.assertGreaterEqual(len(originals), 1)

        for path in originals:
            with self.subTest(scenario=path.parent.name):
                copy = shipped / f"{path.parent.name}.json"
                self.assertTrue(copy.is_file(), "not shipped")
                self.assertEqual(
                    copy.read_bytes(),
                    path.read_bytes(),
                    "the shipped copy is not the file it will be labelled as",
                )

    def test_no_shipped_scenario_is_an_orphan(self) -> None:
        """A file the site serves under a repository path must still exist."""
        for copy in sorted((GENERATED / "scenarios").glob("*.json")):
            with self.subTest(scenario=copy.stem):
                self.assertTrue((ROOT / "scenarios" / copy.stem / "scenario.json").is_file())


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class CountingClaimTests(unittest.TestCase):
    """
    Counts the site states, against what it is counting.

    The README said "twenty-one subjects" ten lines above its own "40/40
    verdicts correct", having grown by nineteen without the sentence moving.
    A marketing site is a larger surface of the same hazard, so its numbers are
    read from the repository rather than written into it.
    """

    def test_the_scenario_export_matches_the_scenarios_on_disk(self) -> None:
        exported = json.loads((GENERATED / "scenarios.json").read_text(encoding="utf-8"))
        on_disk = sorted(p.parent.name for p in (ROOT / "scenarios").glob("*/scenario.json"))
        self.assertEqual(sorted(s["slug"] for s in exported), on_disk)

    def test_the_baseline_export_matches_the_baselines_on_disk(self) -> None:
        exported = json.loads((GENERATED / "baselines.json").read_text(encoding="utf-8"))
        on_disk = sorted(p.name for p in (ROOT / "baselines").glob("*.json"))
        self.assertEqual(sorted(b["file"] for b in exported), on_disk)

    def test_the_facts_export_counts_what_it_claims_to_count(self) -> None:
        """
        Every number the marketing pages display, against its source.

        These are the figures a visitor reads as fact: how many scenarios ship,
        how many adversarial subjects there are, how many of them currently
        produce the wrong verdict.
        """
        facts = json.loads((GENERATED / "facts.json").read_text(encoding="utf-8"))
        subjects = json.loads(MANIFEST.read_text(encoding="utf-8"))["subjects"]

        self.assertEqual(facts["subjects"], len(subjects))
        self.assertEqual(
            facts["scenarios"],
            len(list((ROOT / "scenarios").glob("*/scenario.json"))),
        )
        self.assertEqual(
            facts["subjects_with_open_defects"],
            sum(1 for case in subjects if case["currently"] != case["should_be"]),
        )
        self.assertEqual(sum(facts["subjects_by_expected_verdict"].values()), len(subjects))
        self.assertEqual(sum(facts["scenarios_by_grading"].values()), facts["scenarios"])
        # The document lists are checked against git rather than the directory,
        # by `test_the_docs_page_only_advertises_committed_files`. Asserting the
        # glob here as well would be two rules for one fact, and the weaker of
        # the two would win whenever an untracked file appeared.
        self.assertTrue(facts["docs"], "no documents exported")
        self.assertTrue(facts["surveys"], "no surveys exported")

    def test_the_docs_page_only_advertises_committed_files(self) -> None:
        """
        Every card links to `blob/main/...`, so an untracked file is a dead link.

        Counting the directory made the number honest about the folder and the
        page dishonest about the site: a scratch file dropped into `docs/`
        became a published card pointing at a URL that cannot resolve, carrying
        the fallback blurb because nobody had written one for a file nobody
        meant to publish.
        """
        facts = json.loads((GENERATED / "facts.json").read_text(encoding="utf-8"))
        for directory, key in (("docs", "docs"), ("conformance", "surveys")):
            listed = subprocess.run(
                ["git", "-C", str(ROOT), "ls-files", f"{directory}/*.md"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.split()
            with self.subTest(directory=directory):
                self.assertEqual(facts[key], sorted(Path(n).name for n in listed))

    def test_every_advertised_document_has_a_description(self) -> None:
        """
        A card reading "See the repository" is a card nobody wrote.

        The generated-counts design protects the count. It cannot protect the
        contents, so this does: a file that reaches the page without a blurb
        fails here rather than shipping the fallback.
        """
        facts = json.loads((GENERATED / "facts.json").read_text(encoding="utf-8"))
        # The blurbs moved out of the screen when a second design started
        # rendering the same list — a card is described in one place now, and
        # this reads that place rather than whichever screen happens to import
        # it.
        source = (SRC / "screens" / "marketing" / "docs-index.ts").read_text(encoding="utf-8")
        described = set(re.findall(r'"([\w.-]+\.md)":', source))

        for name in facts["docs"] + facts["surveys"]:
            with self.subTest(document=name):
                self.assertIn(name, described, "would render the fallback blurb")

    def test_the_facts_export_states_no_test_or_coverage_count(self) -> None:
        """
        The README gives a floor for both, not a figure, because an exact count
        is wrong as soon as somebody writes a test. A website repeating one
        would be worse: nothing on the page could correct it.
        """
        facts = json.loads((GENERATED / "facts.json").read_text(encoding="utf-8"))
        for banned in ("tests", "test_count", "coverage", "branch_coverage"):
            with self.subTest(key=banned):
                self.assertNotIn(banned, facts)

    def test_no_hand_written_count_of_subjects_or_scenarios(self) -> None:
        """
        A number in the authored copy is a number that can drift.

        The site derives every count it displays from the exports above, so a
        digit written into the prose layer is either wrong now or will be.

        This used to read `copy.ts` alone, which is where the *scenario cards'*
        prose lives — and every other authored sentence on the site was
        invisible to it. Four of them said "seven scenarios": a terminal
        comment on the home page and three section leads. All four would have
        gone stale the day an eighth shipped, with nothing failing.

        Comments are stripped first. A docstring explaining that seven
        scenarios ship is documentation, not a claim rendered at a visitor.
        """
        surfaces = [
            path
            for tree in SOURCE_TREES
            if tree.is_dir()
            for path in sorted(tree.rglob("*.tsx"))
            if "screens" in path.parts
        ] + [SRC / "data" / "copy.ts"]
        for path in surfaces:
            text = " ".join(_without_comments(path.read_text(encoding="utf-8")).split())
            for pattern in (
                r"\b(?:\d+|forty|twenty[- ]one|seven)\s+(?:adversarial\s+)?subjects\b",
                r"\b(?:\d+|seven)\s+scenarios\b",
                r"\bthe\s+seven\s+that\s+ship\b",
                r"\bthe\s+same\s+seven\b",
            ):
                with self.subTest(file=path.relative_to(ROOT), pattern=pattern):
                    self.assertIsNone(
                        re.search(pattern, text, re.IGNORECASE),
                        "counts belong in generated data, not in authored prose",
                    )


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class LimitationTests(unittest.TestCase):
    """
    Limitations ship inside the evidence bundle, so they ship inside the UI.

    `LimitationsBlock` renders `evidence.limitations` — the strings
    `beacon/runner.py` writes — and has no prop that turns it off.
    """

    def test_the_bundles_carry_the_runner_limitations(self) -> None:
        expected = re.findall(r'^\s*"((?:[^"\\]|\\.)*not a safety certification\.)",', RUNNER.read_text(encoding="utf-8"), re.M)
        self.assertTrue(expected, "the runner's limitation text moved; repoint this guard")

        for path in sorted(GENERATED.glob("*/evidence.json")):
            with self.subTest(run=path.parent.name):
                limitations = json.loads(path.read_text(encoding="utf-8"))["limitations"]
                self.assertIn(expected[0], limitations)

    def test_the_limitations_block_cannot_be_dismissed(self) -> None:
        """
        The absence of a close affordance is the specification.

        Comments are stripped first. The component's own docstring explains why
        there is no `onDismiss`, and a guard that cannot tell an explanation
        from an implementation would forbid saying so.
        """
        source = _without_comments(
            (SRC / "components" / "verdict" / "LimitationsBlock.tsx").read_text(
                encoding="utf-8"
            )
        )
        for forbidden in ("onDismiss", "collapsed", "onClose"):
            with self.subTest(prop=forbidden):
                self.assertNotIn(forbidden, source)


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class MarkTests(unittest.TestCase):
    """
    The tab icon, against the component it is a copy of.

    `public/mark.svg` is a hand-maintained duplicate of `Mark.tsx` — the
    favicon is a file the browser fetches, so it cannot be the component. That
    makes it the one asset in the site that drifts silently: it shipped with a
    hardcoded near-black fill and the component's large-size stroke weight,
    which on a dark tab strip was dark grey on dark grey, and nothing rendered
    wrongly anywhere a test was looking.
    """

    SVG = SRC.parent / "public" / "mark.svg"
    COMPONENT = SRC / "components" / "shell" / "Mark.tsx"

    def _paths(self, source: str) -> list[str]:
        return re.findall(r'd="([^"]+)"', source)

    def test_the_icon_is_well_formed_xml(self) -> None:
        """
        Two consecutive hyphens are illegal inside an XML comment, and an SVG
        that explains itself by naming a CSS custom property contains a pair.
        The failure is a broken-image icon in the tab, not a wrong colour.
        """
        from xml.dom.minidom import parseString

        parseString(self.SVG.read_text(encoding="utf-8"))

    def test_the_icon_and_the_component_draw_the_same_mark(self) -> None:
        svg = self._paths(self.SVG.read_text(encoding="utf-8"))
        component = self._paths(self.COMPONENT.read_text(encoding="utf-8"))
        self.assertEqual(len(svg), 3, "the icon should have three arcs")
        self.assertEqual(
            svg,
            component,
            "the favicon and the wordmark have drifted apart",
        )

    def test_the_icon_follows_the_browser_theme(self) -> None:
        """
        Not a style preference. A fixed dark fill is invisible on a dark tab
        strip, which is where this started.
        """
        source = self.SVG.read_text(encoding="utf-8")
        self.assertIn("prefers-color-scheme: dark", source)
        self.assertIn("currentColor", source)
        # A literal colour outside the two <style> declarations means some part
        # of the mark cannot follow the theme.
        without_style = re.sub(r"<style>.*?</style>", "", source, flags=re.S)
        self.assertEqual(
            re.findall(r"#[0-9a-fA-F]{3,8}", without_style),
            [],
            "a hardcoded colour cannot invert with the tab strip",
        )


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class AssertionCopyTests(unittest.TestCase):
    """
    The plain-English sentence shown for each assertion, pinned to the
    assertions that actually exist.

    `assertionSentences` and `assertionNotes` fall back to the assertion's own
    `description` when there is no entry, which is what lets a new assertion
    appear on screen without being written in. The cost of that fallback is
    that a renamed or deleted assertion leaves a key behind that matches
    nothing, and nothing on screen looks wrong — the sentence a person wrote is
    simply never shown again. This is the check that notices.
    """

    COPY = SRC / "data" / "copy.ts"

    def _keys(self, table: str) -> set[str]:
        source = self.COPY.read_text(encoding="utf-8")
        body = re.search(
            rf"export const {table}: Record<string, string> = \{{(.*?)^\}};",
            source,
            re.S | re.M,
        )
        self.assertIsNotNone(body, f"{table} moved or changed shape; repoint this guard")
        return set(re.findall(r'^\s*"([^"]+)":', body.group(1), re.M))

    def _known(self) -> tuple[set[str], set[str]]:
        """Every assertion id, bare and qualified by its scenario."""
        scenarios = json.loads((GENERATED / "scenarios.json").read_text(encoding="utf-8"))
        bare = {a["id"] for s in scenarios for a in s["assertions"]}
        qualified = {f'{s["id"]}:{a["id"]}' for s in scenarios for a in s["assertions"]}
        return bare, qualified

    def test_there_are_assertions_to_check(self) -> None:
        bare, _ = self._known()
        self.assertGreater(len(bare), 10, "the scenario export carries no assertions")

    def test_every_sentence_and_note_names_a_real_assertion(self) -> None:
        bare, qualified = self._known()
        for table in ("assertionSentences", "assertionNotes"):
            for key in sorted(self._keys(table)):
                with self.subTest(table=table, key=key):
                    self.assertIn(
                        key,
                        bare | qualified,
                        f"{key} matches no assertion in any shipped scenario",
                    )

    def test_an_id_used_by_two_scenarios_is_never_keyed_bare(self) -> None:
        """
        A bare key is a claim that the sentence is true of every scenario using
        that id. `protected-never-read` guards a message in one scenario and a
        personnel record in another; keyed bare, the document run said the
        agent had not read "the protected message", which that scenario does
        not contain. Ids appearing in more than one scenario must be qualified.
        """
        scenarios = json.loads((GENERATED / "scenarios.json").read_text(encoding="utf-8"))
        homes: dict[str, set[str]] = {}
        for scenario in scenarios:
            for assertion in scenario["assertions"]:
                homes.setdefault(assertion["id"], set()).add(scenario["id"])

        shared = {
            assertion_id: sorted(owners)
            for assertion_id, owners in homes.items()
            if len(owners) > 1
        }
        self.assertTrue(shared, "no assertion id is shared; this guard has nothing to hold")

        # Ids that mean the same thing wherever they appear, and so are allowed
        # one sentence between them. Each is a statement about the run itself
        # rather than about the scenario's subject matter.
        SCENARIO_NEUTRAL = {"task-completed", "within-call-budget"}

        for table in ("assertionSentences", "assertionNotes"):
            keys = self._keys(table)
            for assertion_id, owners in sorted(shared.items()):
                if assertion_id in SCENARIO_NEUTRAL:
                    continue
                with self.subTest(table=table, assertion=assertion_id):
                    self.assertNotIn(
                        assertion_id,
                        keys,
                        f"{assertion_id} is used by {', '.join(owners)} and must be "
                        f"keyed as '<scenario id>:{assertion_id}'",
                    )


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class QualifyingCaveatTests(unittest.TestCase):
    """
    The places the site would otherwise claim more than the repository does.

    Each of these shipped missing once. A capability table without its caveat
    reads as an inventory; a digest printed bare reads as tamper-proofing; a
    redaction described without its limit reads as a guarantee. None of those
    are lies anyone wrote — they are what the reader supplies when the sentence
    stops early.

    The check is for the load-bearing word rather than the sentence, so the
    prose can be rewritten but not dropped.
    """

    # The two entries that used to head this tuple guarded a compatibility
    # table with four rungs, of which the fourth — a native runtime adapter
    # collecting configuration, approvals, cost and richer traces — was
    # aspiration. They were removed with the design that carried the table.
    # The site now lists the five adapters that exist and nothing above them,
    # so there is no overreach left to qualify; had the table survived without
    # its caveat, this is where that would have been caught.
    CAVEATS = (
        ("components/verdict/VerdictBanner.tsx", "unsigned", "that the digest is not a signature"),
        # `project-beacon verify` now exists, so "no command checks one yet" stopped
        # being true and was replaced. What did not change is the limitation
        # underneath it: recomputing a hash shows the file is intact, and
        # nothing about who produced it.
        ("components/verdict/VerdictBanner.tsx", "regenerate both", "that the digest proves no provenance"),
        ("screens/playground/ExportBundle.tsx", "exact-value", "that redaction is matching, not a guarantee"),
        ("components/shell/EmptyState.tsx", "mistaken for a finding", "why an empty screen stays empty"),
    )

    def test_every_qualifying_caveat_is_still_on_its_surface(self) -> None:
        for path, phrase, what in self.CAVEATS:
            with self.subTest(file=path, states=what):
                text = (SRC / path).read_text(encoding="utf-8")
                self.assertIn(phrase, text, f"the caveat stating {what} is gone")


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class CertificationLanguageTests(unittest.TestCase):
    """
    A passing report is evidence for one synthetic scenario.

    This applies to tooltips, alt text and page titles, not only body copy,
    which is why it reads every source file rather than the visible strings.
    """

    BANNED = ("certified", "verified safe", "approved", "guarantees safety")

    def test_there_are_sources_to_read(self) -> None:
        self.assertGreater(len(_site_sources()), 10)

    def test_no_certification_language_anywhere_in_the_site(self) -> None:
        for path in _site_sources():
            if GENERATED in path.parents:
                continue  # recorded output, not something the site says
            text = path.read_text(encoding="utf-8").lower()
            for phrase in self.BANNED:
                with self.subTest(file=path.relative_to(ROOT), phrase=phrase):
                    self.assertNotIn(phrase, text)

    def test_no_social_proof_component_exists(self) -> None:
        """
        Nothing to fill in later means no pressure to invent it.

        There is no logo wall, counter, testimonial or badge in this system,
        and this fails if one is added.
        """
        names = {p.stem.lower() for p in SRC.rglob("*.tsx")}
        for banned in ("testimonial", "logowall", "logocloud", "trustedby", "socialproof"):
            with self.subTest(component=banned):
                self.assertNotIn(banned, names)


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class SocialCardTests(unittest.TestCase):
    """
    The Open Graph tags, against the page title and description they repeat.

    They have to be a second copy — a crawler reads the served HTML and will
    not run the app — and a second copy of a sentence is the shape that drifts.
    Nothing else on this site states a fact twice without a test between the
    copies.
    """

    INDEX = SITE / "index.html"

    def _meta(self, attribute: str, name: str, page: Path | None = None) -> str:
        source = _without_comments((page or self.INDEX).read_text(encoding="utf-8"))
        match = re.search(
            rf'<meta\s+{attribute}="{re.escape(name)}"\s+content="([^"]*)"',
            source,
            re.S,
        ) or re.search(
            rf'<meta\s*\n?\s*{attribute}="{re.escape(name)}"\s*\n?\s*content="([^"]*)"',
            source,
            re.S,
        )
        self.assertIsNotNone(match, f"no <meta {attribute}={name}>")
        return " ".join(match.group(1).split())

    def test_the_card_repeats_the_page_title(self) -> None:
        source = self.INDEX.read_text(encoding="utf-8")
        title = re.search(r"<title>(.*?)</title>", source, re.S)
        self.assertIsNotNone(title)
        self.assertEqual(self._meta("property", "og:title"), " ".join(title.group(1).split()))

    def test_the_card_repeats_the_page_description(self) -> None:
        self.assertEqual(
            self._meta("property", "og:description"),
            self._meta("name", "description"),
        )

    def test_every_entry_point_carries_a_matching_card(self) -> None:
        """
        Each design is a separate document, so each needs its own tags — and
        each is a second copy of a sentence, which is the shape that drifts.
        """
        for name in ENTRY_POINTS:
            page = SITE / name
            if not page.is_file():
                continue
            with self.subTest(page=name):
                source = _without_comments(page.read_text(encoding="utf-8"))
                title = re.search(r"<title>(.*?)</title>", source, re.S)
                self.assertIsNotNone(title, "no <title>")
                self.assertEqual(
                    self._meta("property", "og:title", page),
                    " ".join(title.group(1).split()),
                )
                self.assertEqual(
                    self._meta("property", "og:description", page),
                    self._meta("name", "description", page),
                )
                self.assertNotIn("og:image", source)
                self.assertEqual(self._meta("name", "twitter:card", page), "summary")

    def test_the_card_declares_no_image(self) -> None:
        """
        `summary`, not `summary_large_image`, and no `og:image`.

        There is no picture on this site, and a card that promises one renders
        as a broken card rather than a small one.
        """
        source = _without_comments(self.INDEX.read_text(encoding="utf-8"))
        self.assertNotIn("og:image", source)
        self.assertEqual(self._meta("name", "twitter:card"), "summary")


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class VisualVocabularyTests(unittest.TestCase):
    """
    The design rules `tokens.css` states in prose, made executable.

    Every rule here was already written down and enforced by nothing. This
    repository's own position, from `tests/test_falsifiability.py`, is that a
    rule without a check is a suggestion — and these are the ones a redesign
    would break first, quietly, while everything still looked fine.
    """

    def test_gradients_stay_semantic(self) -> None:
        """
        `tokens.css`: "FLAKY is a mix of the two hues rather than a fourth one.
        A new colour would imply a fourth kind of answer."

        Two exemptions, both load-bearing rather than convenient. The hatch
        utilities are the semantic use the rule is about. A mask gradient is
        not paint at all: it is an alpha ramp, it introduces no hue, and so it
        cannot be mistaken for a fourth kind of answer — which is the entire
        thing this rule exists to prevent.

        That second exemption used to be written as the literal `mask-image`,
        justified by the sanctioned scroll cue being built from one. Both parts
        were too narrow. React spells the property `maskImage`, so the guard was
        blind to every mask an inline style declared — the same camelCase hole
        the raster guard had — and the scroll cue was never the reason, only the
        first instance. The rule below is the one the reasoning supports: a
        gradient may be a mask, in any spelling, and may not be paint.
        """
        mask = re.compile(r"(?:-webkit-)?mask-image|(?:Webkit)?[Mm]askImage")
        for path in _site_sources():
            if path.suffix not in {".css", ".tsx", ".ts"}:
                continue
            source = _without_comments(path.read_text(encoding="utf-8"))
            for match in re.finditer(r"gradient", source):
                window = source[max(0, match.start() - 160) : match.end() + 40]
                if "hatch-flaky" in window or mask.search(window):
                    continue
                with self.subTest(file=path.relative_to(ROOT), at=match.start()):
                    self.fail(
                        "a gradient that is paint rather than the FLAKY hatch or a mask; "
                        "gradient is a verdict vocabulary in this system"
                    )

    #: Tailwind's named weights, so a class can be checked against the ceiling.
    NAMED_WEIGHTS = {
        "font-thin": 100,
        "font-extralight": 200,
        "font-light": 300,
        "font-normal": 400,
        "font-medium": 500,
        "font-semibold": 600,
        "font-bold": 700,
        "font-extrabold": 800,
        "font-black": 900,
    }

    def _ceiling_for(self, tree: Path) -> int:
        """
        The heaviest weight the `@font-face` rules in one tree provide.

        Derived rather than written down, and derived **per tree**. The first
        version of this took the maximum across the whole site, which quietly
        made it weaker than the constant it replaced: while two designs shipped
        at once, one could fetch Archivo at 700 and let the other ask for a
        synthesised bold from a face that stops at 500, and this guard would
        have said nothing. A ceiling is a fact about the faces a given page
        loads, so it is computed from the stylesheet that page uses.

        A tree that declares no faces of its own inherits the entry's, which is
        what `src/` does now: it holds the shared playground and components, is
        imported by `src-b/`, and renders under whichever stylesheet the
        document loaded. A ceiling of zero there would fail every weight in it.

        `font-weight: 400 500` is a variable range, so the second number is the
        ceiling; a single value is its own ceiling.
        """
        heaviest = 0
        for path in sorted(tree.rglob("fonts*.css")):
            for declaration in re.findall(
                r"font-weight:\s*([0-9\s]+);", path.read_text(encoding="utf-8")
            ):
                heaviest = max(heaviest, *(int(n) for n in declaration.split()))
        if heaviest:
            return heaviest
        return max(
            (
                self._weights_in(other)
                for other in SOURCE_TREES
                if other != tree and other.is_dir()
            ),
            default=0,
        )

    @staticmethod
    def _weights_in(tree: Path) -> int:
        """The heaviest `@font-face` weight declared in one tree, or zero."""
        heaviest = 0
        for path in sorted(tree.rglob("fonts*.css")):
            for declaration in re.findall(
                r"font-weight:\s*([0-9\s]+);", path.read_text(encoding="utf-8")
            ):
                heaviest = max(heaviest, *(int(n) for n in declaration.split()))
        return heaviest

    @staticmethod
    def _tree_of(path: Path) -> Path:
        """Which source tree a file belongs to; entry points map to their own."""
        for tree in SOURCE_TREES:
            if tree in path.parents:
                return tree
        return SITE / "src-b"

    def test_the_shipped_fonts_are_discoverable(self) -> None:
        """
        A ceiling of zero would make the guard below pass on anything.

        Read through `_ceiling_for`, so a tree carrying no faces of its own is
        held to the ones the document actually loads rather than to nothing.
        """
        for tree in SOURCE_TREES:
            if not tree.is_dir():
                continue
            with self.subTest(tree=tree.name):
                self.assertGreaterEqual(
                    self._ceiling_for(tree), 400, "no @font-face weights found in this tree"
                )

    def test_no_weight_the_fonts_cannot_render(self) -> None:
        ceilings = {tree: self._ceiling_for(tree) for tree in SOURCE_TREES if tree.is_dir()}
        numeric = re.compile(r"font-weight:\s*(\d{3})\b")
        named = re.compile(r"\b(font-(?:thin|extralight|light|normal|medium|semibold|bold|extrabold|black))\b")

        for path in _site_sources():
            source = _without_comments(path.read_text(encoding="utf-8"))
            # The @font-face declarations are the source of the ceiling, not a
            # use of it.
            if path.name.startswith("fonts") and path.suffix == ".css":
                continue
            ceiling = ceilings.get(self._tree_of(path), 0)

            for weight in numeric.findall(source):
                with self.subTest(file=path.relative_to(ROOT), weight=weight):
                    self.assertLessEqual(
                        int(weight),
                        ceiling,
                        f"the shipped fonts stop at {ceiling}; this is synthesised",
                    )
            for name in named.findall(source):
                with self.subTest(file=path.relative_to(ROOT), weight=name):
                    self.assertLessEqual(
                        self.NAMED_WEIGHTS[name],
                        ceiling,
                        f"{name} is {self.NAMED_WEIGHTS[name]}; the shipped fonts stop at {ceiling}",
                    )

    def test_full_bleed_never_uses_the_viewport_width(self) -> None:
        """
        `100vw` includes the classic scrollbar, so it makes the document wider
        than the viewport — which `tools/visual.mjs` fails on. The sanctioned
        bleed is a section with no max-width wrapping a div that has one.
        """
        pattern = re.compile(r"100vw|w-screen|-translate-x-1/2")
        for path in _site_sources():
            source = _without_comments(path.read_text(encoding="utf-8"))
            with self.subTest(file=path.relative_to(ROOT)):
                self.assertIsNone(
                    pattern.search(source),
                    "use a full-width section around a max-width div, not the viewport",
                )

    def test_faint_text_never_lands_on_the_sunken_surface(self) -> None:
        """
        `--text-faint` measures 4.78 on `--sunken` in light mode — under AA,
        and `tokens.css` says so in the token's own comment. The contrast test
        verifies the number; this stops the pairing being used.
        """
        for path in SRC.rglob("*.tsx"):
            source = _without_comments(path.read_text(encoding="utf-8"))
            for value in re.findall(r'className=[{"]?["`]([^"`]+)["`]', source):
                if "bg-sunken" in value and "text-text-faint" in value:
                    with self.subTest(file=path.relative_to(ROOT)):
                        self.fail("--text-faint on --sunken is 4.78 in light mode")

    def test_no_motion_that_outlives_reduced_motion(self) -> None:
        """
        `tokens.css` kills CSS animation and transition globally — and nothing
        else. SMIL, `scroll-behavior` and JS timers all run straight through
        it, so a visitor who asked for no motion still gets it.

        The playground timeline is the one sanctioned timer: the visitor
        pressed Run, and the reveal is content rather than decoration.
        """
        # A path, not a basename. As a basename, any file anywhere called
        # RunTimeline.tsx inherited the exemption — including one in a second
        # design tree that had never earned it.
        allowed = {SRC / "screens" / "playground" / "RunTimeline.tsx"}
        pattern = re.compile(r"<animate|<set\s|scroll-behavior|setInterval|requestAnimationFrame")
        for path in SRC.rglob("*.tsx"):
            if path in allowed:
                continue
            source = _without_comments(path.read_text(encoding="utf-8"))
            with self.subTest(file=path.relative_to(ROOT)):
                self.assertIsNone(
                    pattern.search(source),
                    "prefers-reduced-motion does not stop this; it is CSS-only",
                )

    def test_the_site_ships_no_raster_images(self) -> None:
        """
        The rule the five design mocks follow and no test enforced.

        All five specify zero imagery — no `<img>`, no canvas, no
        background-image, no photograph or illustration anywhere. That was a
        decision, not an omission: "No invented proof… There is nothing to fill
        in later." Until now an AI-generated hero could have been committed and
        the whole suite would have stayed green.

        Beyond taste, a raster is the one artifact here that cannot be pinned.
        Every other claim is hashed or counted against a source in the
        repository; a picture has no source to compare to, so it can go stale
        the day the fixtures are re-recorded with nothing noticing.
        """
        rasters = [
            p
            for p in (SITE / "public").rglob("*")
            if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif"}
        ]
        self.assertEqual(rasters, [], "the site ships vector and text only")

        # Both spellings. React inline styles are camelCase, so a JSX
        # `style={{ backgroundImage: ... }}` slipped past a check that only
        # knew the CSS casing — which is most of how a background would
        # actually arrive in this codebase.
        painted = re.compile(r"background-image|backgroundImage")
        for path in _site_sources():
            source = _without_comments(path.read_text(encoding="utf-8"))
            with self.subTest(file=path.relative_to(ROOT)):
                self.assertNotIn("<img", source)
                self.assertIsNone(painted.search(source), "a painted background")


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class HeadlineTests(unittest.TestCase):
    """
    The claim the home page leads with, against the runs it is about.

    The headline is that five recorded agents leave the mailbox in an
    identical state and still earn three different verdicts — so a harness
    that grades by diffing before and after calls all five the same agent.
    That is the strongest thing this project can say, and it is the one
    sentence on the site whose truth depends on five separate bundles
    continuing to agree.

    Every other number here is derived at render time and cannot go stale. A
    headline cannot be derived — somebody wrote it — so it is pinned instead.
    If a subject is re-recorded and the runs stop agreeing, the page is making
    a false claim and the build should say so rather than the sentence quietly
    outliving its evidence.
    """

    SCENARIO = "inbox-briefing-draft-only"

    @classmethod
    def setUpClass(cls) -> None:
        index = json.loads((GENERATED / "index.json").read_text(encoding="utf-8"))
        keys = [f["key"] for f in index["fixtures"] if f["scenario"] == cls.SCENARIO]
        cls.runs = {
            key: json.loads((GENERATED / key / "evidence.json").read_text(encoding="utf-8"))
            for key in keys
        }

    def test_there_are_runs_to_compare(self) -> None:
        self.assertGreaterEqual(
            len(self.runs), 3, "too few recorded runs for the headline to mean anything"
        )

    def test_every_run_leaves_the_same_state(self) -> None:
        """
        The load-bearing half. One end state across all of them.

        Compared as `(before, after, diff)` rather than on the after digest
        alone: two runs could coincidentally agree on a digest while having
        changed different things along the way, and the claim is about the
        report a diff-only harness would produce, which is the whole tuple.
        """
        shapes = {
            (
                run["state"]["before_digest"],
                run["state"]["after_digest"],
                json.dumps(run["state_diff"], sort_keys=True),
            )
            for run in self.runs.values()
        }
        self.assertEqual(
            len(shapes),
            1,
            "the runs no longer share one end state; the home page headline is false",
        )

    def test_the_verdicts_disagree(self) -> None:
        """Identical state is only interesting if the answers differ."""
        verdicts = {run["result"] for run in self.runs.values()}
        self.assertEqual(
            verdicts,
            {"PASS", "FAIL", "INCOMPLETE"},
            "the headline says three different answers",
        )

    def test_one_run_passes_every_assertion_and_is_not_a_pass(self) -> None:
        """
        The sharpest line on the page, and the easiest to lose.

        `disconnects` satisfies all nine assertions and still resolves
        INCOMPLETE, because the host went away before signalling completion.
        It is the clearest statement the site has that INCOMPLETE is not a soft
        failure — and it survives only as long as some run has that shape.
        """
        unmeasured = [
            key
            for key, run in self.runs.items()
            if run["result"] != "PASS" and all(a["passed"] for a in run["assertions"])
        ]
        self.assertTrue(
            unmeasured,
            "no run passes every assertion without being a PASS; that sentence must go",
        )


def _luminance(hex_colour: str) -> float:
    """Relative luminance, WCAG 2.x."""
    value = hex_colour.lstrip("#")
    channels = [int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    first, second = _luminance(a), _luminance(b)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class ContrastTests(unittest.TestCase):
    """
    The contrast ratios `tokens.css` publishes, against the colours it defines.

    Eighteen ratios are written into that file as comments — `/* 5.92 */`,
    `/* 5.04 bg · 5.21 surface · 4.78 sunken */` — and until now every one of
    them was a claim with nothing behind it. The file itself says why that
    matters: "Ratios in the comments are measured against the mode's own --bg.
    A token's published ratio only holds on the backgrounds it was measured
    against." A number that quietly stops being true is exactly the defect this
    repository writes tests about everywhere else.

    This recomputes each one from the hex literals in the same block. It is the
    only check in the project that reads a comment as a specification, which is
    worth doing here because the comment is the only place the measurement
    lives.
    """

    #: Every token file that publishes ratios, with the blocks to read from it.
    #:
    #: A second design used to be listed here alongside this one, on the
    #: reasoning that a palette nothing reads is a palette shipping unverified
    #: numbers. That design is the one that survived; the tuple stays a tuple
    #: so adding another does not mean rewriting the guard.
    #:
    #: It keeps both its palettes in one block, under `--ink-*` and
    #: `--paper-*`, and the blocks that follow only say which is the page and
    #: which is the alternating band in a given theme. Every published ratio
    #: names the ground it was measured against, because two are in scope at
    #: once.
    TOKEN_BLOCKS = ((SITE / "src-b" / "tokens-b.css", r":root", "b"),)
    #: Ratios are quoted to two decimals, so anything inside half a unit of the
    #: last place is the same measurement rounded, not a different one.
    TOLERANCE = 0.05

    #: A bare number means this token, which is the convention the first
    #: file's header states. The second design names its ground explicitly.
    DEFAULT_SURFACE = "bg"

    def _blocks(self) -> dict[str, str]:
        blocks = {}
        for path, selector, name in self.TOKEN_BLOCKS:
            if not path.is_file():
                continue
            match = re.search(
                rf"^{selector} \{{(.*?)^\}}", path.read_text(encoding="utf-8"), re.S | re.M
            )
            self.assertIsNotNone(match, f"the {name} token block moved; repoint this guard")
            blocks[name] = match.group(1)
        return blocks

    @staticmethod
    def _declarations(block: str) -> dict[str, str]:
        return {
            name: value
            for name, value in re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6})\s*;", block)
        }

    def _claims(self, block: str) -> list[tuple[str, str, float]]:
        """Every `(token, surface, ratio)` a comment in this block asserts."""
        found = []
        for token, comment in re.findall(
            r"--([a-z-]+):\s*#[0-9a-fA-F]{6}\s*;\s*/\*([^*]+)\*/", block
        ):
            body = comment.split("—")[0]  # drop trailing notes like "non-text use only"
            for chunk in body.split("·"):
                parts = chunk.split()
                if not parts:
                    continue
                try:
                    ratio = float(parts[0])
                except ValueError:
                    continue
                surface = parts[1] if len(parts) > 1 else self.DEFAULT_SURFACE
                found.append((token, surface, ratio))
        return found

    def test_there_are_ratios_to_check(self) -> None:
        """A guard that parsed nothing would pass silently forever."""
        total = sum(len(self._claims(block)) for block in self._blocks().values())
        self.assertGreaterEqual(
            total, 16, "far fewer published ratios than expected; the comment format changed"
        )

    def test_every_published_ratio_is_the_measured_one(self) -> None:
        for mode, block in self._blocks().items():
            colours = self._declarations(block)
            for token, surface, claimed in self._claims(block):
                with self.subTest(mode=mode, token=token, against=surface):
                    # The surface has to be a token declared in the same block.
                    # A fixed list of legal names could not describe a second
                    # design's grounds without being edited, and a name that is
                    # merely spelled correctly proves nothing — this way a
                    # ratio can only be measured against a colour that exists.
                    self.assertIn(token, colours)
                    self.assertIn(
                        surface, colours, f"{surface} is not a colour declared in this block"
                    )
                    actual = _contrast(colours[token], colours[surface])
                    self.assertAlmostEqual(
                        actual,
                        claimed,
                        delta=self.TOLERANCE,
                        msg=(
                            f"--{token} on --{surface} in {mode} measures {actual:.2f}, "
                            f"and the comment says {claimed:.2f}"
                        ),
                    )

    def test_body_text_clears_the_readable_threshold(self) -> None:
        """
        The two tokens that carry prose, against WCAG AA for normal text.

        `--text-disabled` is exempt and says so in its own comment: it is
        marked non-text use only, and 3.23 would fail this.
        """
        #: Each ground, with the two tokens that carry prose on it. The second
        #: design keeps both its palettes in one block, so a single pair of
        #: names would silently check one ground and skip the other — which is
        #: the ground a light visitor is reading.
        GROUNDS = (
            ("bg", "text", "text-muted"),
            ("b-bg", "b-text", "b-muted"),
            ("ink-bg", "ink-text", "ink-muted"),
            ("paper-bg", "paper-text", "paper-muted"),
        )
        checked = 0
        for mode, block in self._blocks().items():
            colours = self._declarations(block)
            for ground, *prose in GROUNDS:
                if ground not in colours:
                    continue
                for token in prose:
                    with self.subTest(mode=mode, ground=ground, token=token):
                        self.assertGreaterEqual(_contrast(colours[token], colours[ground]), 4.5)
                        checked += 1
        # Renaming a token must not turn this into a loop over nothing. Two
        # grounds with two prose tokens each is what one design with two
        # palettes provides; it was eight when two designs shipped at once.
        self.assertGreaterEqual(checked, 4, "far fewer prose colours checked than expected")


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class PrivacyPolicyTests(unittest.TestCase):
    """
    The legal pages quote CSP directives by name. Nothing checked they were the
    directives the site actually sends.

    That gap had already produced a false statement once: turning on Web
    Analytics required relaxing `connect-src` from `'none'` to `'self'`, and
    both pages still said `'none'` and "runs no analytics" until the copy was
    changed by hand in the same commit. Quoting a directive is the strongest
    form the claim can take — it is checkable — but only if something checks it.
    """

    #: Every page that describes the policy, in each design.
    #: One page now. It was two while a replacement design was reviewed
    #: against the one it replaced, and both had to say the same thing about
    #: the same policy — which is exactly the duplication this class exists to
    #: police. It stays a tuple so a second surface cannot be added silently.
    LEGAL_PAGES = (SITE / "src-b" / "sections" / "LegalScreen.tsx",)

    def _policy(self) -> dict[str, str]:
        config = json.loads((SITE / "vercel.json").read_text(encoding="utf-8"))
        for rule in config.get("headers", []):
            for header in rule.get("headers", []):
                if header["key"].lower() == "content-security-policy":
                    return {
                        directive.split(" ", 1)[0]: directive
                        for directive in (
                            part.strip() for part in header["value"].split(";")
                        )
                        if directive
                    }
        self.fail("no Content-Security-Policy in site/vercel.json")

    def test_every_directive_a_page_quotes_is_one_the_site_sends(self) -> None:
        policy = self._policy()
        quoted = 0
        for page in self.LEGAL_PAGES:
            # Comments are stripped first. The page's own header explains that
            # `connect-src` was relaxed from 'none' to 'self' and why — which a
            # scanner reading the raw file counts as the page claiming 'none'.
            # A guard that punishes writing the reason down is a guard that
            # gets the reason deleted.
            text = _without_comments(page.read_text(encoding="utf-8"))
            # As written in JSX, where the apostrophes may be entities.
            text = text.replace("&apos;", "'").replace("&#x27;", "'")
            for name, actual in policy.items():
                for match in re.finditer(rf"\b{re.escape(name)} '[a-z]+'", text):
                    quoted += 1
                    with self.subTest(page=page.name, directive=name):
                        self.assertEqual(
                            match.group(0),
                            actual,
                            f"{page.name} says {match.group(0)!r}, "
                            f"but vercel.json sends {actual!r}",
                        )
        # Two directives on one page. It was four across two while a
        # replacement design was under review, and the floor moved down with
        # the design rather than being left where a loop over nothing would
        # still clear it.
        self.assertGreaterEqual(
            quoted, 2, "far fewer directives quoted than expected — has the copy moved?"
        )

    def test_a_page_that_can_send_anything_discloses_what(self) -> None:
        """
        `connect-src 'none'` is self-evidently private and needs no disclosure.
        Anything looser does, and the two must not drift apart: this is what
        turns a policy change into a documentation change automatically.
        """
        connect = self._policy().get("connect-src", "")
        for page in self.LEGAL_PAGES:
            text = page.read_text(encoding="utf-8")
            # `assertIn` against a whole source file prints the whole source
            # file. The verdict is what matters here, not the haystack.
            with self.subTest(page=page.name):
                if connect == "connect-src 'none'":
                    self.assertTrue(
                        "no analytics" in text,
                        f"{page.name} does not say the site runs no analytics, "
                        f"which {connect} makes true and worth saying",
                    )
                    continue
                self.assertFalse(
                    "runs no analytics" in text,
                    f"{page.name} claims no analytics, but {connect} permits sending",
                )
                for disclosure in ("Vercel Web Analytics", "/_vercel/insights/view"):
                    self.assertTrue(
                        disclosure in text,
                        f"{connect} permits sending and {page.name} "
                        f"does not disclose {disclosure!r}",
                    )


if __name__ == "__main__":
    unittest.main()
