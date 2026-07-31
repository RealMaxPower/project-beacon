from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.in"
PYPROJECT = ROOT / "pyproject.toml"
TESTS = ROOT / "tests"

# `ROOT / "examples"`, `ROOT / ".github"` — how a test names a directory that
# has to survive into the source distribution.
ROOT_REFERENCE = re.compile(r'ROOT\s*/\s*"([^"]+)"')


def _directories_the_suite_needs() -> set[str]:
    """
    Every top-level directory the shipped tests reach for, read from the tests.

    Derived rather than listed, so a new test that depends on a new directory
    is covered the moment it is written, the same way `_action_required_count`
    derives its expectation from the fixture instead of restating it.
    """
    needed: set[str] = set()
    for path in TESTS.rglob("*.py"):
        for name in ROOT_REFERENCE.findall(path.read_text(encoding="utf-8")):
            candidate = ROOT / name
            if candidate.is_dir():
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


if __name__ == "__main__":
    unittest.main()
