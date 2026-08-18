from __future__ import annotations

import hashlib
import html as html_module
import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DIST = SITE / "dist"
SCENARIOS = SITE / "src" / "data" / "generated" / "scenarios.json"

#: The sentence a scenario page shows when nothing was recorded against it.
#: Written once in `site/src/data/copy.ts` and asserted here by value, so the
#: page and the meta description cannot drift apart again.
NO_RECORDED_RUN = "No recorded run ships for it yet"


def _text(html: str) -> str:
    """
    What a visitor actually reads: no head, no scripts, no markup.

    The distinction is the whole point of this module. Every scenario page has
    always carried its own `<title>`, its own meta description and its own
    JSON-LD; what none of them carried was a body that said which scenario it
    was. A check that looks at the whole document passes on exactly the defect
    it was written to catch, because the promise is in the head.
    """
    body = re.search(r"<body\b[^>]*>(.*)</body>", html, re.S | re.I)
    inner = body.group(1) if body else html
    inner = re.sub(r"<(script|style)\b.*?</\1>", " ", inner, flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", inner)).strip()


@unittest.skipUnless(DIST.is_dir(), "the site has not been built in this checkout")
class ScenarioPageTests(unittest.TestCase):
    """
    Every scenario page is about its own scenario.

    Eighty-three scenarios ship, the build writes a page for each, and each page
    got a unique title, a unique description and a unique sitemap entry. The
    bodies were another matter: stripped of head and markup, the eighty-three
    pages had **eight** distinct bodies between them, seventy-six of them
    identical, and **none** of the eighty-three contained the name of the
    scenario it was serving. `/playground/payments-rollback` promised "The first
    payment landed and the second cannot" in the tab and rendered a generic
    wizard that said "payment" zero times.

    Two cowork audits found it from the outside. Nothing in this repository
    could have, which is what these tests are for.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))
        cls.pages = {}
        for scenario in cls.scenarios:
            page = DIST / "playground" / scenario["id"] / "index.html"
            if page.is_file():
                cls.pages[scenario["id"]] = page.read_text(encoding="utf-8")

    def test_the_build_wrote_a_page_for_every_scenario(self) -> None:
        """Everything below is vacuous if the pages are not there to read."""
        self.assertGreater(len(self.scenarios), 0, "no scenarios to check")
        self.assertEqual(
            sorted(self.pages), sorted(s["id"] for s in self.scenarios),
            "a scenario ships without a page, or a page ships without a scenario",
        )

    def test_every_scenario_page_has_a_body_of_its_own(self) -> None:
        """
        Eight distinct bodies across eighty-three pages is seventy-six
        documents that differ only in their metadata.
        """
        seen: dict[str, list[str]] = {}
        for scenario_id, html in self.pages.items():
            digest = hashlib.sha256(_text(html).encode()).hexdigest()
            seen.setdefault(digest, []).append(scenario_id)

        shared = {d: ids for d, ids in seen.items() if len(ids) > 1}
        self.assertEqual(
            shared,
            {},
            "these scenario pages render an identical body: "
            + "; ".join(", ".join(sorted(ids)) for ids in shared.values()),
        )

    def test_every_scenario_page_names_its_own_scenario(self) -> None:
        """
        The headline defect, stated as the thing a reader would notice.

        Matched on the scenario's name rather than its id: `inbox-briefing` is
        the slug and `inbox-briefing-draft-only` is the id, and the page
        correctly shows the former. An id check would fail on the one scenario
        with the most recorded runs, for being right.
        """
        missing = []
        for scenario in self.scenarios:
            html = self.pages.get(scenario["id"])
            if html is None:
                continue
            body = _text(html).lower()
            if scenario["name"].lower() not in body and scenario["slug"] not in body:
                missing.append(scenario["id"])

        self.assertEqual(missing, [], f"these pages never name their scenario: {missing}")

    def test_the_heading_is_the_page_and_not_the_site(self) -> None:
        """
        Every playground document — the index and all eighty-three scenarios —
        emitted the same `<h1>`, so the one element heading navigation and
        search engines lean on hardest identified nothing.
        """
        headings = {}
        for scenario_id, html in self.pages.items():
            found = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
            self.assertIsNotNone(found, f"{scenario_id} renders no h1")
            headings.setdefault(re.sub(r"<[^>]+>", "", found.group(1)).strip(), []).append(
                scenario_id
            )

        shared = {h: ids for h, ids in headings.items() if len(ids) > 1}
        self.assertEqual(shared, {}, f"these scenario pages share an h1: {shared}")

    def test_the_heading_is_the_one_the_tab_promises(self) -> None:
        """
        The head and the body say the same thing, or the tab is advertising a
        page that does not exist behind it. Enforceable only because the
        prerenderer and the page now compose from the same `scenarioBrief`.

        Entities are resolved on both sides before comparing. React escapes an
        apostrophe in the body as `&#x27;` while the prerenderer interpolates
        the same question into `<title>` as itself, so three scenarios whose
        questions contain "agent's" or "week's" differed only in spelling of a
        character — a mismatch about encoding, not about the two saying
        different things, and the guard should not report it as one.
        """
        for scenario_id, html in self.pages.items():
            with self.subTest(scenario=scenario_id):
                h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
                title = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
                self.assertIsNotNone(h1)
                self.assertIsNotNone(title)
                heading = html_module.unescape(re.sub(r"<[^>]+>", "", h1.group(1))).strip()
                self.assertIn(heading, html_module.unescape(title.group(1)))

    def test_a_page_with_no_recorded_run_says_so_and_one_with_a_run_does_not(self) -> None:
        """
        Both directions. Asserting only that the sentence appears would pass on
        a build that pasted it onto all eighty-three, including the seven whose
        runs you can actually replay.
        """
        recorded = {
            f["scenario"]
            for f in json.loads(
                (SITE / "src" / "data" / "generated" / "index.json").read_text(encoding="utf-8")
            )["fixtures"]
        }
        self.assertGreater(len(recorded), 0, "no recorded runs found to compare against")
        self.assertLess(len(recorded), len(self.pages), "every scenario has a run; nothing to check")

        for scenario_id, html in self.pages.items():
            with self.subTest(scenario=scenario_id):
                body = _text(html)
                if scenario_id in recorded:
                    self.assertNotIn(NO_RECORDED_RUN, body)
                else:
                    self.assertIn(NO_RECORDED_RUN, body)

    def test_a_page_with_no_recorded_run_offers_no_run(self) -> None:
        """
        The seventy-six were handed to step two of the wizard — "Which agent
        should try it?" — over an empty grid, because the step filters recorded
        bundles down to none for these. The page asked a question it had no
        answers for.
        """
        recorded = {
            f["scenario"]
            for f in json.loads(
                (SITE / "src" / "data" / "generated" / "index.json").read_text(encoding="utf-8")
            )["fixtures"]
        }
        for scenario_id, html in self.pages.items():
            if scenario_id in recorded:
                continue
            with self.subTest(scenario=scenario_id):
                self.assertNotIn("Which agent should try it?", _text(html))

    def test_every_scenario_page_can_be_reached_by_clicking(self) -> None:
        """
        The sitemap listed all eighty-three and the site linked one.

        The cards were `<button>` elements with no `href` and the rest were
        plain text in a disclosure, so eighty-two scenario pages could not be
        opened in a new tab, copied, shared, or found by a crawler that follows
        links. A sitemap answers indexability; it does not answer whether a
        reader can get there.
        """
        hrefs: set[str] = set()
        for page in DIST.rglob("*.html"):
            hrefs |= set(
                re.findall(r'href="/playground/([^"#?]+)"', page.read_text(encoding="utf-8"))
            )
        self.assertGreater(len(hrefs), 0, "no playground links found anywhere; check the selector")

        orphans = [s["id"] for s in self.scenarios if s["id"] not in hrefs]
        self.assertEqual(orphans, [], f"{len(orphans)} scenario pages nothing links to: {orphans}")


@unittest.skipUnless(DIST.is_dir(), "the site has not been built in this checkout")
class SitemapTests(unittest.TestCase):
    """
    The sitemap carries the signal crawlers use, not the one they ignore.

    It emitted `<priority>` on all eighty-seven entries and `<lastmod>` on none,
    which is exactly backwards: every major crawler ignores priority, and
    lastmod is what it schedules re-fetches from.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.xml = (DIST / "sitemap.xml").read_text(encoding="utf-8")

    def test_it_has_entries_to_check(self) -> None:
        self.assertGreater(self.xml.count("<loc>"), 0)

    def test_priority_is_gone(self) -> None:
        self.assertNotIn("<priority>", self.xml)

    def test_every_entry_carries_a_lastmod(self) -> None:
        """
        Every entry, whenever the date is knowable.

        The skip is conditioned on git, not on the sitemap. Reading the output
        to decide whether to check the output is the shape of a guard that
        cannot fail: a build emitting no `lastmod` at all — the exact state
        this was written to catch — would have satisfied it by skipping, and
        the first version of this test did precisely that.

        The prerenderer omits the date rather than invent one when git cannot
        answer, because CI checks out with no history and a date taken from the
        clock would claim every page changed the moment the build ran. So when
        git can answer here, so must the sitemap.
        """
        try:
            subprocess.run(
                ["git", "log", "-1", "--format=%cI"],
                cwd=ROOT,
                capture_output=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("no git history in this checkout to date the pages from")

        locs = self.xml.count("<loc>")
        self.assertGreater(locs, 0, "no entries to check")
        self.assertEqual(
            self.xml.count("<lastmod>"),
            locs,
            "git can date this build, so every sitemap entry should carry lastmod",
        )


@unittest.skipUnless(SITE.is_dir(), "the site has not been built in this checkout")
class SharedSentenceTests(unittest.TestCase):
    """
    The no-recorded-run sentence is written once.

    Skipped without `site/`, which the source distribution does not carry. The
    guard in `test_packaging.py` grants that exemption only to a directory a
    module both binds to a name and guards with `skipUnless(NAME.is_dir())` —
    reading it unguarded, as this class first did, makes `site/` a directory the
    shipped suite requires, and the sdist would have had to grow a React
    application to satisfy it.

    The prerenderer composed it for the meta description and the markdown twin,
    and the body composed nothing at all — which is how eighty-three documents
    came to promise a scenario in the head that the body never mentioned. Two
    copies of a sentence are two sentences waiting to disagree.
    """

    def test_it_appears_once_in_the_source(self) -> None:
        found = []
        for tree in ("src", "src-b", "tools"):
            for path in (SITE / tree).rglob("*"):
                if path.suffix in {".ts", ".tsx"} and NO_RECORDED_RUN in path.read_text(
                    encoding="utf-8"
                ):
                    found.append(str(path.relative_to(SITE)))
        self.assertEqual(
            found,
            ["src/data/copy.ts"],
            "the sentence is defined somewhere other than copy.ts, or twice",
        )


if __name__ == "__main__":
    unittest.main()
