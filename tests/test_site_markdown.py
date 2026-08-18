from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
DIST = SITE / "dist"
PRERENDER = SITE / "tools" / "prerender.tsx"
CONVERTER = SITE / "tools" / "to-markdown.ts"
PAGES = SITE / "src-b" / "pages.ts"


@unittest.skipUnless(DIST.is_dir(), "the site has not been built in this checkout")
class MarkdownTwinTests(unittest.TestCase):
    """
    Every page is also served as markdown, and it says the same thing.

    TIME serves assistant crawlers a separate markdown edition of its site with
    sponsored blocks in it that no reader ever sees, decided by User-Agent.
    This is the other half of that idea without the half that makes it a
    problem: the same content, in a lighter format, at a URL anyone can open.

    The property that keeps it honest is not the intention, it is this file. A
    machine-readable copy that can drift from the human one is two sets of
    claims with one of them unreviewed — the failure this project exists to
    refuse, and a failure that would be invisible to anyone looking at the
    site.
    """

    def _twins(self) -> list[tuple[Path, Path]]:
        """Each HTML document with the markdown alongside it."""
        found = []
        for html in sorted(DIST.rglob("index.html")):
            relative = html.parent.relative_to(DIST)
            twin = DIST / ("index.md" if relative == Path(".") else f"{relative}.md")
            found.append((html, twin))
        return found

    @staticmethod
    def _prose(html: str) -> str:
        body = re.search(r"<body.*?>(.*)</body>", html, re.S)
        # Both tags, and case-insensitively, because that is what
        # `site/tools/to-markdown.ts` does when it writes the twin. This used
        # to strip only `<script>`, in lower case, so a page with an inline
        # `<style>` would have counted its CSS as prose and disagreed with a
        # twin that correctly dropped it.
        #
        # The closing tag allows what HTML allows, which `to-markdown.ts` now
        # matches: `</script >` closes a script and so does `</script foo>`,
        # while `</scriptx>` does not. A comparison between two strippers is
        # only as good as the weaker one — if this half keeps a script body the
        # twin correctly dropped, the test reports drift that is its own, and if
        # it drops one the twin kept, it stays silent about drift that is real.
        text = re.sub(
            r"<(script|style)\b[^>]*>.*?</\1(?=[\s>])[^>]*>",
            " ", body.group(1) if body else "",
            flags=re.S | re.I,
        )
        return " ".join(re.sub(r"<[^>]+>", " ", text).split())

    def test_the_prose_reader_agrees_with_a_browser_about_what_is_script(self) -> None:
        """
        The stripper above, on the markup code scanning raised it for.

        `py/bad-tag-filter` was right twice over. The pattern demanded the exact
        spelling `</script>`, so anything else removed both tags and left the
        body behind as prose — and "anything else" is wider than it first looks:
        an end tag runs through the same attribute parsing an opening tag does
        and simply ignores what it finds, so `</script >` and
        `</script foo="bar">` both close a script. Allowing only whitespace was
        the first fix and closed half the hole. This function decides whether a
        twin has drifted, and a stripper that publishes a script body invents
        drift that is its own rather than the page's.

        The negative case is checked in the same breath, because the obvious
        over-correction — matching anything after the tag name — makes
        `</scriptx>` end a script that HTML leaves open, which puts the body
        back in the prose by the opposite route.

        The second is the one worth writing down. Remove the inner element of
        `<sc<script>x</script>ript>POISON</script>` and the text left behind
        reads `<script>POISON</script>`, which is why the rule wants the removal
        looped. But Chromium given that markup builds no script element at all
        and renders `xript>POISON` as ordinary words — checked, not assumed.
        Looping would delete text a reader can see in order to hide a script
        that was never there, so the loop is refused and this pins the refusal.
        """
        for description, markup, expected in (
            ("a closing tag spelled with a space",
             "<p>KEEP</p><script >POISON</script >", False),
            # An end tag runs through the same attribute parsing an opening tag
            # does and ignores what it finds, so these close a script too. `\s*`
            # was the first fix here and caught only the case above it.
            ("a closing tag carrying an attribute",
             '<p>KEEP</p><script>POISON</script foo="bar">', False),
            ("a closing tag broken across whitespace",
             "<p>KEEP</p><script>POISON</script\t\n bar>", False),
            # The other side of the same line: a longer name is a different tag,
            # so a pattern loose enough to match it would end the script early
            # and start publishing the script body again.
            ("a longer tag name, which closes nothing",
             "<p>KEEP</p><script>POISON</scriptx>", True),
            ("markup that only looks like a completed script",
             "<p>KEEP</p><sc<script>x</script>ript>POISON</script>", True),
        ):
            with self.subTest(case=description):
                prose = self._prose(f"<body>{markup}</body>")
                # A stripper returning "" would satisfy every assertNotIn ever
                # made of it, so both directions are checked on every input.
                self.assertIn("KEEP", prose, "the prose reader dropped ordinary text")
                if expected:
                    self.assertIn("POISON", prose, f"{description}: a browser shows this text")
                else:
                    self.assertNotIn("POISON", prose, f"{description}: a script body became prose")

    def test_there_are_twins_to_check(self) -> None:
        self.assertGreaterEqual(len(self._twins()), 4)

    def test_every_page_has_one(self) -> None:
        for html, twin in self._twins():
            with self.subTest(page=html.parent.name or "/"):
                self.assertTrue(twin.is_file(), f"{twin.name} was not generated")

    def test_every_page_advertises_it(self) -> None:
        """A twin nothing links to is a file, not an alternate representation."""
        for html, twin in self._twins():
            with self.subTest(page=html.parent.name or "/"):
                self.assertIn('rel="alternate" type="text/markdown"', html.read_text(encoding="utf-8"))

    def test_the_twin_is_smaller_or_it_has_no_purpose(self) -> None:
        """
        The entire reason for the format. If a twin is not substantially
        lighter than its page, it is a second copy of the site earning nothing.
        """
        for html, twin in self._twins():
            with self.subTest(page=html.parent.name or "/"):
                self.assertLess(
                    twin.stat().st_size,
                    html.stat().st_size * 0.6,
                    "the markdown is not meaningfully lighter than the HTML",
                )

    def test_the_twin_carries_the_page_it_is_a_twin_of(self) -> None:
        """
        Not a diff — the formats differ by design — but a floor. A converter
        that silently dropped a section would leave the twin much shorter than
        the prose it was made from, and a model would be reading a page the
        site does not serve.
        """
        for html, twin in self._twins():
            with self.subTest(page=html.parent.name or "/"):
                prose = self._prose(html.read_text(encoding="utf-8"))
                markdown = twin.read_text(encoding="utf-8")
                self.assertGreater(len(markdown), len(prose) * 0.5)

    def test_the_twin_names_the_page_it_stands_for(self) -> None:
        """Front matter, so a model quoting it has something to cite."""
        for _html, twin in self._twins():
            body = twin.read_text(encoding="utf-8")
            with self.subTest(page=twin.name):
                self.assertTrue(body.startswith("---\n"))
                self.assertRegex(body, r"(?m)^canonical: https://\S+$")

    def test_the_caveat_survives_the_conversion(self) -> None:
        """
        The one sentence that must reach a model reading this site instead of
        the page. An answer engine that quotes Beacon without it is repeating
        the overstatement the whole repository exists to prevent.
        """
        for _html, twin in self._twins():
            with self.subTest(page=twin.name):
                self.assertIn("not a safety certification", twin.read_text(encoding="utf-8"))

    def test_the_answers_reach_a_model_intact(self) -> None:
        """The FAQ is the part most likely to be quoted, so it is checked."""
        source = PAGES.read_text(encoding="utf-8")
        block = source[source.index("export const FAQ"):]
        answers = re.findall(r'a:\s*\n?\s*"(.*?)",\n\s*\}', block, re.S)
        self.assertGreaterEqual(len(answers), 5)

        landing = (DIST / "index.md").read_text(encoding="utf-8")
        for answer in answers:
            # As it appears in prose: the source escapes quotes and backslashes.
            expected = answer.replace('\\"', '"').replace("\\\\", "\\")
            with self.subTest(answer=expected[:40]):
                self.assertIn(expected, landing)


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class NoAudienceSplitTests(unittest.TestCase):
    """
    Nothing here decides what to serve by who is asking.

    That is the whole distinction between an alternate format and a private
    edition, and it is one line of code away at any time — a `User-Agent`
    check at the edge, in a middleware, in the config. This is the check that
    makes the absence deliberate rather than merely current.
    """

    def test_no_user_agent_is_consulted_anywhere_it_could_fork_a_response(self) -> None:
        surfaces = [SITE / "vercel.json", *sorted((SITE / "src-b").rglob("*.ts*"))]
        surfaces += [p for p in sorted((SITE / "tools").iterdir()) if p.is_file()]
        offenders = []
        for path in surfaces:
            body = path.read_text(encoding="utf-8")
            # Comments explain why this is forbidden and must not trip it.
            body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
            body = re.sub(r"^\s*//.*$", "", body, flags=re.M)
            body = re.sub(r"^\s*#.*$", "", body, flags=re.M)
            # Reading it, specifically. `robots.txt` is generated from a
            # template containing the literal `User-agent:` directive, which is
            # the opposite of a fork: it is the policy, in the open.
            if re.search(r"userAgent|headers\s*[\[(]\s*[\"']user-agent", body, re.I):
                offenders.append(str(path.relative_to(SITE)))
        self.assertEqual(
            offenders,
            [],
            "something reads the User-Agent; a response that varies by who is "
            "asking is a second site nobody reviews",
        )

    def test_the_policy_allows_the_assistant_crawlers_by_name(self) -> None:
        """
        `User-agent: *` already permits them. Naming them records that it was
        decided rather than defaulted — and makes a later refusal a visible
        edit rather than an absence nobody notices.
        """
        robots = (DIST / "robots.txt").read_text(encoding="utf-8") if (DIST / "robots.txt").is_file() else ""
        if not robots:
            self.skipTest("the site has not been built in this checkout")
        for bot in ("GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot"):
            with self.subTest(bot=bot):
                self.assertIn(bot, robots)
        self.assertNotIn("Disallow:", robots)

    def test_the_converter_is_ours_rather_than_a_dependency(self) -> None:
        """
        A general HTML converter would handle markup this site never emits and
        fail silently the day it did. This one covers a closed vocabulary, and
        the tests above are what say it covers it.
        """
        self.assertTrue(CONVERTER.is_file())
        packaged = json.loads((SITE / "package.json").read_text(encoding="utf-8"))
        for name in ("turndown", "html-to-md", "node-html-markdown", "jsdom"):
            self.assertNotIn(name, packaged.get("dependencies", {}))
        self.assertIn("toMarkdown", PRERENDER.read_text(encoding="utf-8"))


class TagFilterCaseTests(unittest.TestCase):
    """
    The script filter and the check on it shared one blind spot.

    `_prose` strips `<script>` before comparing a page against its markdown
    twin, and `site/tools/to-markdown.ts` strips it before writing that twin.
    Both regexes were case-sensitive, so `<SCRIPT>` passed through the stripper
    *and* through the check written to catch it — a guard that could not fail
    for the reason it exists.

    No content in this repository uses an uppercase tag, so nothing was
    leaking. It is worth fixing anyway because of what this project ships:
    scenarios carrying deliberate injection payloads, at four obfuscation
    rungs, one of which is markup. Case-variance is the obvious next rung, and
    the markdown twins are served specifically to language models.
    """

    def test_the_stripper_does_not_care_about_case(self) -> None:
        for tag in ("script", "SCRIPT", "ScRiPt", "STYLE"):
            with self.subTest(tag=tag):
                html = f"<body>keep<{tag}>alert(1)</{tag}>keep</body>"
                self.assertNotIn("alert(1)", MarkdownTwinTests._prose(html))

    def test_the_stripper_still_keeps_the_prose(self) -> None:
        self.assertIn("keep", MarkdownTwinTests._prose("<body>keep</body>"))


if __name__ == "__main__":
    unittest.main()
