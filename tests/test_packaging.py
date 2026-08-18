from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.in"
PYPROJECT = ROOT / "pyproject.toml"
TESTS = ROOT / "tests"

# `ROOT / "examples"`, `ROOT / ".github"` — how a test names a directory that
# has to survive into the source distribution.
ROOT_REFERENCE = re.compile(r'ROOT\s*/\s*"([^"]+)"')

# A module-level binding of a directory to a name, so the skip guard below can
# be matched against that same name. Written without an example of the pattern
# it matches: this file is itself scanned, and a sample in a comment would be
# read as a real dependency — which is how this line got its own bug.
NAMED_REFERENCE = re.compile(r'^(\w+)\s*=\s*ROOT\s*/\s*"([^"]+)"', re.M)


def _optional_directories(source: str) -> set[str]:
    """
    Directories a test file reads but is written to run without.

    There is a third category between "the sdist must carry this" and "no test
    touches it": a directory that is part of the repository but not part of the
    distribution, whose tests skip cleanly when it is absent. `site/` is the
    first — it holds a React application and ten woff2 files, which have no
    business inside `pip install project-beacon`, but its numbers are pinned by
    the Python suite because that is what stops them drifting.

    The exemption is deliberately narrow. It is granted only to a directory the
    file both binds to a name and guards with `skipUnless(NAME.is_dir())` —
    mentioning a skip somewhere in the file is not enough. A test that reads a
    directory unconditionally still requires it to be packaged, which is the
    original guarantee and the one that matters.
    """
    optional: set[str] = set()
    for variable, directory in NAMED_REFERENCE.findall(source):
        guard = rf"skipUnless\(\s*{re.escape(variable)}\.is_dir\(\)"
        if re.search(guard, source):
            optional.add(directory)
    return optional


def _directories_the_suite_needs() -> set[str]:
    """
    Every top-level directory the shipped tests reach for, read from the tests.

    Derived rather than listed, so a new test that depends on a new directory
    is covered the moment it is written, the same way `_action_required_count`
    derives its expectation from the fixture instead of restating it.

    A directory is required if *any* file reads it without a skip guard, so one
    unguarded test is enough to put it back on the list.
    """
    needed: set[str] = set()
    for path in TESTS.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        skippable = _optional_directories(source)
        for name in ROOT_REFERENCE.findall(source):
            if (ROOT / name).is_dir() and name not in skippable:
                needed.add(name)
    return needed


def _manifest_directives() -> str:
    return MANIFEST.read_text(encoding="utf-8")


def _declared_packages() -> set[str]:
    """
    Top-level names `pyproject.toml` already ships as importable packages.

    These reach the sdist through `[tool.setuptools] packages`, so requiring a
    `recursive-include` for them would be asking the manifest to repeat what
    the build backend is already told.
    """
    text = PYPROJECT.read_text(encoding="utf-8")
    block = re.search(r"^packages\s*=\s*\[(.*?)\]", text, re.M | re.S)
    if not block:
        return set()
    return {name.split(".")[0] for name in re.findall(r'"([^"]+)"', block.group(1))}


class SourceDistributionTests(unittest.TestCase):
    """
    The sdist must carry what the suite it ships needs to run.

    Without a `MANIFEST.in`, setuptools shipped `beacon/`, `scenarios/`,
    `tests/test_*.py`, the README and the LICENSE — and stopped. Twelve test
    files reached for `examples/` or `schemas/`, `tests/stubs/` was dropped
    because it is data rather than a `test_*.py`, and `.github/` went with it,
    so a suite advertised as the project's guarantee could not start.

    Nothing noticed because the release workflow's smoke test only ran
    `--version`, `scenarios`, `validate`, `run` and `init` — the exact subset
    that survives the omission.
    """

    def test_a_manifest_exists(self) -> None:
        self.assertTrue(
            MANIFEST.exists(),
            "without MANIFEST.in the sdist silently drops examples/ and schemas/",
        )

    def test_the_scan_found_dependencies_to_check(self) -> None:
        """A passing check that examined nothing proves nothing."""
        needed = _directories_the_suite_needs()
        self.assertIn("examples", needed)
        self.assertIn("schemas", needed)
        self.assertGreaterEqual(len(needed), 3)

    def test_the_skip_guard_exemption_is_real(self) -> None:
        """
        An escape hatch nobody checks is a hole.

        `_optional_directories` lets a test read a directory the sdist does not
        carry, provided it skips when the directory is absent. That is only
        sound while the guard it looks for is the guard the test actually has,
        so this asserts both halves against the one file using it.
        """
        site_test = TESTS / "test_site_claims.py"
        if not site_test.exists():
            self.skipTest("nothing uses the exemption")

        source = site_test.read_text(encoding="utf-8")
        self.assertIn("site", _optional_directories(source))
        self.assertRegex(source, r"skipUnless\(\s*SITE\.is_dir\(\)")
        self.assertNotIn("site", _directories_the_suite_needs())

    def test_an_unguarded_read_is_still_required(self) -> None:
        """The exemption must not be granted to a file that merely mentions one."""
        self.assertEqual(_optional_directories('X = ROOT / "docs"'), set())
        self.assertEqual(
            _optional_directories('X = ROOT / "docs"\n# skipUnless(Y.is_dir())'),
            set(),
        )
        self.assertEqual(
            _optional_directories('X = ROOT / "docs"\n@unittest.skipUnless(X.is_dir(), "")'),
            {"docs"},
        )

    def test_every_directory_the_suite_reads_is_packaged(self) -> None:
        directives = _manifest_directives()
        packaged = _declared_packages()
        missing = [
            name
            for name in sorted(_directories_the_suite_needs() - packaged)
            if not re.search(
                rf"^recursive-include\s+{re.escape(name)}\s", directives, re.M
            )
        ]
        self.assertEqual(
            missing,
            [],
            f"MANIFEST.in does not ship {missing}, which the shipped tests read",
        )

    def test_the_tests_own_data_files_are_packaged(self) -> None:
        """`tests/stubs/` is not a `test_*.py`, so nothing ships it by default."""
        self.assertTrue((TESTS / "stubs" / "anthropic.py").exists())
        self.assertRegex(
            _manifest_directives(), r"(?m)^recursive-include\s+tests\s.*\*\.json"
        )

    def test_the_documentation_ships(self) -> None:
        for name in ("docs", "schemas"):
            with self.subTest(directory=name):
                self.assertRegex(
                    _manifest_directives(),
                    rf"(?m)^recursive-include\s+{name}\s",
                )


class BuildRequirementTests(unittest.TestCase):
    """
    The declared setuptools floor must actually support the metadata in use.

    `pyproject.toml` writes its licence as a PEP 639 SPDX expression with
    `license-files`, which setuptools only understands from 77.0.0. The floor
    said 69. Every local build passed regardless, because the local setuptools
    is far newer than the floor — the failure only appears in an isolated build
    that honours it, which is the one a publisher runs.
    """

    def test_the_setuptools_floor_supports_pep_639(self) -> None:
        text = PYPROJECT.read_text(encoding="utf-8")
        match = re.search(r'requires\s*=\s*\["setuptools>=(\d+)', text)
        self.assertIsNotNone(match, "the build-system requirement moved")
        self.assertGreaterEqual(
            int(match.group(1)),
            77,
            "PEP 639 license expressions need setuptools 77; an older floor "
            "is a config error in any build that honours it",
        )

    def test_the_licence_really_is_declared_the_pep_639_way(self) -> None:
        """Otherwise the floor above is guarding a requirement nobody has."""
        text = PYPROJECT.read_text(encoding="utf-8")
        self.assertRegex(text, r'(?m)^license\s*=\s*"[^"]+"')
        self.assertRegex(text, r"(?m)^license-files\s*=")


class LongDescriptionTests(unittest.TestCase):
    """
    `README.md` is the package's PyPI description, and PyPI is not GitHub.

    `pyproject.toml` sets `readme = "README.md"`, so every byte of that file is
    published as the project page. A relative path there resolves against
    `pypi.org/project/project-beacon/` rather than against the repository, and
    reaches nothing.

    0.1.0 shipped with 29 of them. The demo image had been converted to an
    absolute URL because `docs/releasing.md` warned about it — a broken image
    is visible — and the twenty-nine links beside it, which fail silently, were
    never asked the same question. A released description cannot be edited, so
    they are wrong on that version permanently.

    This is the check that would have caught the image, the links, and the
    version badge that was added before the package it names existed.
    """

    README = ROOT / "README.md"

    #: `[label](target)` and `![alt](target)` in one pattern.
    LINK = re.compile(r"!?\[([^\]]*)\]\(([^)\s]+)\)")

    def test_nothing_in_the_readme_is_relative(self) -> None:
        found = self.LINK.findall(self.README.read_text(encoding="utf-8"))
        self.assertGreater(len(found), 20, "the README stopped linking anything")
        relative = sorted(
            {
                target
                for _, target in found
                if not target.startswith(("http://", "https://", "mailto:", "#"))
            }
        )
        self.assertEqual(
            relative,
            [],
            "these resolve against pypi.org on the project page and reach "
            f"nothing; make them absolute: {relative}",
        )

    #: The `label-message-colour` payload of a *static* shields.io badge.
    STATIC_BADGE = re.compile(r"https://img\.shields\.io/badge/([^)\s]+)")

    def test_no_static_badge_carries_a_version_number(self) -> None:
        """
        A version typed into a badge is a second place to bump, and the second
        place is the one that gets missed.

        0.1.1 shipped with `status-v0.1.0`: `pyproject.toml` and
        `beacon/__init__.py` moved and the badge beside them did not, so the
        project page for 0.1.1 announced 0.1.0 — permanently, because a
        released description cannot be edited.

        The computed `pypi/v` badge on the line above it already prints the
        version, and prints whatever was actually published rather than
        whatever was last typed. So the rule is that the version appears in
        the badge that is computed and in no badge that is not.
        """
        badges = self.STATIC_BADGE.findall(self.README.read_text(encoding="utf-8"))
        self.assertGreater(len(badges), 0, "this guard found no badges to check")
        carrying = sorted(b for b in badges if re.search(r"\d+\.\d+\.\d+", b))
        self.assertEqual(
            carrying,
            [],
            "a static badge cannot know the version; let the pypi badge print "
            f"it: {carrying}",
        )


class BadgeFactTests(unittest.TestCase):
    """
    The remaining badges assert things with a live source elsewhere.

    A static badge is a claim with no mechanism behind it, and the version one
    proved what that costs: it went stale at 0.1.1 and froze there. These two
    are correct today, and were equally unguarded — the interpreter list has a
    source in the classifiers, and the coverage floor has one in the workflow
    that enforces it. So they are checked against those rather than trusted.
    """

    README = (ROOT / "README.md").read_text(encoding="utf-8")
    WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

    def _badge(self, prefix: str) -> str:
        found = re.search(
            rf"https://img\.shields\.io/badge/{prefix}-([^-]+)-", self.README
        )
        self.assertIsNotNone(found, f"no {prefix} badge in the README to check")
        return unquote(found.group(1))

    def test_the_interpreter_badge_matches_the_classifiers(self) -> None:
        claimed = {part.strip() for part in self._badge("python").split("|")}
        declared = set(
            re.findall(
                r"(?m)^\s*\"Programming Language :: Python :: (\d+\.\d+)\"",
                PYPROJECT.read_text(encoding="utf-8"),
            )
        )
        self.assertTrue(declared, "no versioned classifiers to check against")
        self.assertEqual(claimed, declared)

    def test_the_coverage_badge_matches_the_floor_ci_enforces(self) -> None:
        claimed = re.search(r"(\d+)", self._badge("branch%20coverage"))
        self.assertIsNotNone(claimed, "the coverage badge states no number")
        enforced = re.search(
            r"--fail-under=(\d+)", self.WORKFLOW.read_text(encoding="utf-8")
        )
        self.assertIsNotNone(enforced, "no --fail-under in the workflow")
        self.assertEqual(claimed.group(1), enforced.group(1))


if __name__ == "__main__":
    unittest.main()
