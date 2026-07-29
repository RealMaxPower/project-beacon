from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from beacon.builtins import builtin_names, builtin_root, resolve_scenario
from beacon.models import Scenario


ROOT = Path(__file__).resolve().parents[1]


class BuiltinScenarioTests(unittest.TestCase):
    """
    `pip install project-beacon` used to give a working CLI and nothing to
    point it at: every command in the README names a path under `scenarios/`,
    which exists only in a checkout. The first thing a new user tried failed.
    """

    def test_every_shipped_scenario_is_reachable_by_name(self) -> None:
        on_disk = sorted(
            path.parent.name for path in (ROOT / "scenarios").glob("*/scenario.json")
        )
        self.assertEqual(list(builtin_names()), on_disk)
        self.assertTrue(on_disk, "no scenarios found at all")

    def test_a_name_resolves_to_a_loadable_scenario(self) -> None:
        for name in builtin_names():
            with self.subTest(name=name):
                scenario = Scenario.load(resolve_scenario(name))
                self.assertTrue(scenario.assertions)

    def test_a_path_that_exists_wins_over_a_builtin_of_the_same_name(self) -> None:
        """
        Someone who cloned the repo and edited a scenario must get their copy.
        Preferring the installed one would let them edit a file and see no
        change, which is a maddening thing to debug.
        """
        with tempfile.TemporaryDirectory() as directory:
            local = Path(directory) / "inbox-briefing"
            local.mkdir()
            source = json.loads(
                (ROOT / "scenarios" / "inbox-briefing" / "scenario.json").read_text()
            )
            source["name"] = "Locally edited"
            (local / "scenario.json").write_text(json.dumps(source))
            resolved = resolve_scenario(local / "scenario.json")
            self.assertEqual(Scenario.load(resolved).name, "Locally edited")

    def test_an_unknown_name_lists_what_is_available(self) -> None:
        with self.assertRaises(FileNotFoundError) as caught:
            resolve_scenario("no-such-scenario")
        message = str(caught.exception)
        self.assertIn("inbox-briefing", message)

    def test_a_missing_path_is_reported_as_a_path_not_a_name(self) -> None:
        """
        'scenarios/typo/scenario.json' is a mistyped path, not an attempt to
        name a built-in. Listing the built-ins there would be a confusing
        answer to a question nobody asked.
        """
        with self.assertRaises(FileNotFoundError) as caught:
            resolve_scenario("scenarios/typo/scenario.json")
        self.assertIn("does not exist", str(caught.exception))
        self.assertNotIn("Built-in scenarios:", str(caught.exception))

    def test_the_error_does_not_leak_a_path_repr(self) -> None:
        with self.assertRaises(FileNotFoundError) as caught:
            resolve_scenario(Path("nope"))
        self.assertNotIn("PosixPath", str(caught.exception))
        self.assertNotIn("WindowsPath", str(caught.exception))

    def test_the_checkout_layout_is_found(self) -> None:
        root = builtin_root()
        self.assertIsNotNone(root)
        self.assertTrue((root / "inbox-briefing" / "scenario.json").is_file())


class PackagingTests(unittest.TestCase):
    """
    The build maps `scenarios/` into the package as `beacon/builtin_scenarios`.
    That mapping lives in pyproject.toml and nothing else would notice it
    breaking until someone installed the result.
    """

    def _pyproject(self) -> str:
        return (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    def test_the_scenario_directory_is_mapped_into_the_package(self) -> None:
        text = self._pyproject()
        self.assertIn('"beacon.builtin_scenarios" = "scenarios"', text)
        self.assertIn('"beacon.builtin_scenarios" = ["*/scenario.json"]', text)

    def test_the_mapped_package_is_in_the_package_list(self) -> None:
        """
        Discovered packages and an explicit mapping do not combine: with
        `packages.find` the mapping is silently ignored and the wheel ships
        no scenarios at all. Found by installing the wheel and looking.
        """
        self.assertIn('"beacon.builtin_scenarios",', self._pyproject())

    def test_every_package_directory_is_listed(self) -> None:
        """An explicit package list is a list somebody has to remember to update."""
        text = self._pyproject()
        for path in sorted((ROOT / "beacon").glob("*/__init__.py")):
            name = f"beacon.{path.parent.name}"
            with self.subTest(package=name):
                self.assertIn(f'"{name}",', text)

    def test_the_console_script_points_at_something_callable(self) -> None:
        self.assertIn('beacon = "beacon.cli:main"', self._pyproject())
        from beacon.cli import main

        self.assertTrue(callable(main))

    def test_the_version_agrees_with_the_package(self) -> None:
        from beacon import __version__

        self.assertIn(f'version = "{__version__}"', self._pyproject())


class CommandLineTests(unittest.TestCase):
    def _beacon(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "beacon", *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )

    def test_scenarios_lists_the_builtins(self) -> None:
        result = self._beacon("scenarios")
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in builtin_names():
            self.assertIn(name, result.stdout)

    def test_a_scenario_can_be_validated_by_bare_name(self) -> None:
        result = self._beacon("validate", "inbox-briefing")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"valid": true', result.stdout)

    def test_an_unknown_scenario_name_exits_two(self) -> None:
        result = self._beacon("validate", "no-such-scenario")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Built-in scenarios:", result.stderr)


if __name__ == "__main__":
    unittest.main()
