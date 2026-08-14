from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PAGES = SITE / "src-b" / "pages.ts"
PRERENDER = SITE / "tools" / "prerender.tsx"
VERCEL = SITE / "vercel.json"
QUESTIONS = SITE / "src-b" / "sections" / "Questions.tsx"


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class DiscoverabilityTests(unittest.TestCase):
    """
    The site served zero words and one URL.

    Its content was rendered entirely in the browser, so a crawler that runs no
    JavaScript — which is most of the ones behind answer engines — received an
    empty `<div>`. Its routes were fragments, and a fragment is never sent to a
    server, so `/#/docs` was not an address: three of the four screens did not
    exist to anything indexing, and `robots.txt` and `sitemap.xml` returned the
    landing page as `text/html` because a catch-all rewrite answered every path.

    None of that is visible from the running site, which looked correct the
    whole time. These are the properties that make it true, checked from the
    source rather than from a report.
    """

    def _pages(self) -> list[dict[str, str]]:
        """The page table, read out of the TypeScript that declares it."""
        source = PAGES.read_text(encoding="utf-8")
        table = source[source.index("export const PAGES"):source.index("export function pageFor")]
        return [
            {
                "path": path,
                "title": re.search(r'title:\s*\n?\s*"(.*?)",\n', block, re.S).group(1),
                "description": re.search(r'description:\s*\n?\s*"(.*?)",\n', block, re.S).group(1),
            }
            for path, block in (
                (m.group(1), table[m.start():])
                for m in re.finditer(r'path:\s*"([^"]+)"', table)
            )
        ]

    def test_there_are_pages_to_check(self) -> None:
        self.assertGreaterEqual(len(self._pages()), 4)

    def test_every_page_is_a_real_path_not_a_fragment(self) -> None:
        for page in self._pages():
            with self.subTest(page=page["path"]):
                self.assertTrue(page["path"].startswith("/"))
                self.assertNotIn("#", page["path"])

    def test_no_page_shares_a_title_or_description_with_another(self) -> None:
        """
        Four pages under one title is one page as far as a search engine is
        concerned, and the duplicate is the one that gets dropped.
        """
        pages = self._pages()
        for field in ("title", "description"):
            values = [page[field] for page in pages]
            with self.subTest(field=field):
                self.assertEqual(len(values), len(set(values)))

    def test_titles_and_descriptions_are_the_length_that_survives(self) -> None:
        """
        Not a rule handed down: a title much over 60 characters is truncated in
        a result, and a description under 70 gives an answer engine nothing to
        quote. Both bounds are generous — this catches an empty field or a
        paragraph pasted into one, not a judgement call about wording.
        """
        for page in self._pages():
            with self.subTest(page=page["path"]):
                self.assertGreaterEqual(len(page["title"]), 20)
                self.assertLessEqual(len(page["title"]), 75)
                self.assertGreaterEqual(len(page["description"]), 70)
                self.assertLessEqual(len(page["description"]), 400)

    def test_the_canonical_origin_is_declared_once(self) -> None:
        """
        Canonical, og:url, the sitemap and every `@id` in the structured data
        are the same origin or they contradict each other. There is one
        constant, and this is what stops a second appearing.
        """
        source = PAGES.read_text(encoding="utf-8")
        origins = re.findall(r'SITE_ORIGIN = "([^"]+)"', source)
        self.assertEqual(len(origins), 1)
        self.assertTrue(origins[0].startswith("https://"))
        self.assertFalse(origins[0].endswith("/"), "a trailing slash doubles in every URL built")

        # And nothing else hardcodes an origin that could drift from it.
        for path in sorted((SITE / "src-b").rglob("*.ts*")):
            if path == PAGES:
                continue
            body = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
            with self.subTest(file=path.name):
                self.assertNotIn(origins[0], body)


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class AnswerEngineTests(unittest.TestCase):
    """
    Structured questions have to be questions the page actually answers.

    Marked-up content that does not appear on the page is a claim about a page
    that does not make it. Google names the mismatch as grounds for ignoring
    the markup, and it is the same rule the rest of this project runs on: the
    evidence has to be the thing described.
    """

    def _faq(self) -> list[tuple[str, str]]:
        source = PAGES.read_text(encoding="utf-8")
        block = source[source.index("export const FAQ"):]
        return re.findall(r'\{\s*\n\s*q:\s*"(.*?)",\n\s*a:\s*\n?\s*"(.*?)",\n\s*\}', block, re.S)

    def test_there_are_questions(self) -> None:
        self.assertGreaterEqual(len(self._faq()), 5)

    def test_the_page_renders_the_same_questions_it_marks_up(self) -> None:
        """
        Enforced by construction — one array, read by the section and by the
        structured data — and checked because "by construction" is a claim too.
        """
        rendered = QUESTIONS.read_text(encoding="utf-8")
        self.assertIn('from "../pages"', rendered)
        self.assertIn("FAQ.map", rendered)
        self.assertIn("FAQ", PRERENDER.read_text(encoding="utf-8"))

    def test_every_answer_stands_on_its_own(self) -> None:
        """
        An answer gets quoted without its question in front of it. One that
        opens "It does." or runs to a paragraph of preamble is no use quoted,
        so each is required to be a sentence or three that names its subject.
        """
        for question, answer in self._faq():
            with self.subTest(question=question):
                self.assertGreaterEqual(len(answer), 120, "too short to answer anything")
                self.assertLessEqual(len(answer), 700, "too long to be quoted")
                self.assertTrue(answer.rstrip().endswith("."))

    def test_the_unflattering_answers_are_still_there(self) -> None:
        """
        The two questions this project must answer "no" to. An FAQ that has
        quietly lost them is marketing, and an answer engine repeating it would
        be repeating the overstatement the whole repository exists to prevent.
        """
        answers = {q: a for q, a in self._faq()}
        certification = next(q for q in answers if "certification" in q)
        judge = next(q for q in answers if "judge" in q)
        self.assertTrue(answers[certification].startswith("No."))
        self.assertTrue(answers[judge].startswith("No."))


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class HostRoutingTests(unittest.TestCase):
    """
    What the host does with a URL, which is not visible from the app.

    The catch-all rewrite that made every path render the landing page also
    made every path return 200 — including `robots.txt`, which a crawler then
    parsed as HTML and found no rules in.
    """

    def _config(self) -> dict:
        return json.loads(VERCEL.read_text(encoding="utf-8"))

    def test_no_rewrite_swallows_every_path(self) -> None:
        for rule in self._config().get("rewrites", []):
            with self.subTest(source=rule["source"]):
                self.assertNotIn("(.*)", rule["source"])

    def test_the_old_address_redirects_rather_than_rewriting(self) -> None:
        """
        A rewrite serves one document at another document's URL. With routes
        as paths that is not a synonym for a redirect: the client reads the
        address bar, does not recognise it, and renders not-found over content
        that arrived correctly.
        """
        redirects = self._config().get("redirects", [])
        self.assertTrue(redirects, "the legacy address has nowhere to go")
        for rule in redirects:
            with self.subTest(source=rule["source"]):
                self.assertTrue(rule.get("permanent"), "a temporary redirect is not indexed")

    def test_the_build_prerenders_before_anything_serves_it(self) -> None:
        scripts = json.loads((SITE / "package.json").read_text(encoding="utf-8"))["scripts"]
        self.assertIn("prerender", scripts["build"])

    def test_every_resource_the_page_links_has_a_directive_that_allows_it(self) -> None:
        """
        `default-src 'none'` means every resource type has to be named.

        The manifest was linked and `manifest-src` was not declared, so it fell
        back to `'none'`: the file served 200, the browser refused to use it as
        a manifest, and every page load emitted a violation — on a site whose
        clean console was one of the things an audit had praised.

        This is checked statically rather than by driving a browser, and that
        is the point rather than a shortcut. The obvious runtime check —
        listen for `securitypolicyviolation` and fail on one — was written
        first and could not catch it: headless Chrome never fetches the
        manifest, so removing the directive again left it green. A check that
        cannot fail for the reason it exists is worse than none.
        """
        html = (SITE / "dist" / "index.html").read_text(encoding="utf-8")
        policy = ""
        for rule in self._config()["headers"]:
            for header in rule["headers"]:
                if header["key"].lower() == "content-security-policy":
                    policy = header["value"]
        self.assertTrue(policy, "no Content-Security-Policy to check against")
        self.assertIn("default-src 'none'", policy, "this check assumes a default-deny policy")

        #: What the document links, and the directive that has to name it.
        REQUIRED = (
            (r'<link[^>]+rel="manifest"', "manifest-src"),
            (r'<link[^>]+rel="stylesheet"', "style-src"),
            (r"<script[^>]+src=", "script-src"),
            (r'<link[^>]+rel="icon"', "img-src"),
            (r'<link[^>]+rel="preload"[^>]+as="font"', "font-src"),
        )
        checked = 0
        for pattern, directive in REQUIRED:
            if not re.search(pattern, html):
                continue
            checked += 1
            with self.subTest(directive=directive):
                self.assertRegex(
                    policy,
                    rf"\b{re.escape(directive)}\s",
                    f"the document links a resource governed by {directive}, and the "
                    f"policy does not name it — so it falls back to default-src 'none'",
                )
        self.assertGreaterEqual(checked, 3, "the document links less than expected; has it changed?")

    def test_the_policy_still_forbids_inline_style(self) -> None:
        """
        Prerendering turned styles React had been writing through the CSSOM
        into `style` attributes, which `style-src 'self'` forbids. The fix was
        to lift them into a generated stylesheet; the fix it was not allowed to
        be was `'unsafe-inline'`.
        """
        for rule in self._config()["headers"]:
            for header in rule["headers"]:
                if header["key"].lower() != "content-security-policy":
                    continue
                self.assertIn("style-src 'self'", header["value"])
                self.assertNotIn("unsafe-inline", header["value"])
                self.assertNotIn("unsafe-eval", header["value"])
        self.assertIn("liftInlineStyles", PRERENDER.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
