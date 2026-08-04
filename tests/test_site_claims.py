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
    Drop `/* … */` and `//` comments.

    Several guards below forbid a word appearing in the code. The same word
    usually has to appear in the comment that explains why it is forbidden, and
    a check that cannot tell those apart would punish writing the reason down.
    """
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"^\s*//.*$", "", source, flags=re.M)


def _site_sources() -> list[Path]:
    """Every file the site is built from. Excludes the design mocks."""
    return [
        path
        for path in sorted(SRC.rglob("*"))
        if path.is_file() and path.suffix in SOURCE_SUFFIXES
    ] + [SITE / "index.html"]


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
        source = (SRC / "screens" / "marketing" / "Docs.tsx").read_text(encoding="utf-8")
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
        """
        text = " ".join((SRC / "data" / "copy.ts").read_text(encoding="utf-8").split())
        for pattern in (
            r"\b(?:\d+|forty|twenty[- ]one|seven)\s+(?:adversarial\s+)?subjects\b",
            r"\b(?:\d+|seven)\s+scenarios\b",
        ):
            with self.subTest(pattern=pattern):
                self.assertIsNone(
                    re.search(pattern, text, re.IGNORECASE),
                    "counts belong in generated data, not in copy.ts",
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

    CAVEATS = (
        ("screens/marketing/HowItWorks.tsx", "level 4", "which rungs of the table are real"),
        ("screens/marketing/HowItWorks.tsx", "does not currently collect", "what levels 3-4 do not gather"),
        ("components/verdict/VerdictBanner.tsx", "unsigned", "that the digest is not a signature"),
        ("components/verdict/VerdictBanner.tsx", "verifies", "that no command checks a digest yet"),
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


if __name__ == "__main__":
    unittest.main()
