from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from beacon.models import Scenario, ScenarioError
from beacon.scaffold import scaffold


REPO_ROOT = Path(__file__).resolve().parent.parent


class ScaffoldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_it_writes_a_scenario_and_both_subjects(self) -> None:
        created = scaffold("my-probe", self.root)
        names = {path.name for path in created}
        self.assertEqual(
            names, {"scenario.json", "compliant.py", "violating.py", "README.md"}
        )

    def test_the_service_variant_also_writes_a_service(self) -> None:
        created = scaffold("my-probe", self.root, service="notes")
        self.assertIn("service.py", {path.name for path in created})

    def test_the_generated_scenario_is_valid(self) -> None:
        """A scaffold that does not survive Beacon's own loader is worthless."""
        scaffold("my-probe", self.root)
        scenario = Scenario.load(self.root / "my-probe" / "scenario.json")
        self.assertEqual(scenario.id, "my-probe")
        self.assertTrue(scenario.assertions)

    def test_the_service_scenario_is_valid(self) -> None:
        scaffold("my-probe", self.root, service="notes")
        scenario = Scenario.load(self.root / "my-probe" / "scenario.json")
        self.assertIn("notes", scenario.fixtures)

    def test_the_grounding_subject_only_reads_what_it_is_given(self) -> None:
        """
        Fixtures are the grading ground truth and are withheld from subjects.
        A scaffold that read them would work here and mislead everyone who
        adapted it, since no real subject can.
        """
        scaffold("my-probe", self.root)
        source = (self.root / "my-probe" / "subjects" / "compliant.py").read_text()
        self.assertIn('start["scenario"]["goal"]', source)
        self.assertNotIn('["fixtures"]', source)

    def test_the_report_text_is_in_the_goal_as_well_as_the_fixture(self) -> None:
        scaffold("my-probe", self.root)
        scenario = Scenario.load(self.root / "my-probe" / "scenario.json")
        self.assertIn("checkout-api", scenario.goal)
        self.assertIn("checkout-api", scenario.fixtures["report"]["text"])

    def test_the_generated_service_registers_itself(self) -> None:
        """Otherwise --service-module imports a module that does nothing."""
        scaffold("my-probe", self.root, service="notes")
        source = (self.root / "my-probe" / "service.py").read_text()
        self.assertIn('register_service("notes"', source)

    def test_generated_tool_names_match_the_scenarios_tool_surface(self) -> None:
        scaffold("my-probe", self.root, service="notes")
        scenario = Scenario.load(self.root / "my-probe" / "scenario.json")
        source = (self.root / "my-probe" / "service.py").read_text()
        for tool in scenario.tools:
            self.assertIn(f'"name": "{tool}"', source)

    def test_an_existing_file_is_not_silently_overwritten(self) -> None:
        scaffold("my-probe", self.root)
        with self.assertRaises(ScenarioError):
            scaffold("my-probe", self.root)

    def test_force_overwrites(self) -> None:
        scaffold("my-probe", self.root)
        scaffold("my-probe", self.root, force=True)

    def test_a_bad_scenario_id_is_refused(self) -> None:
        for bad in ("Bad ID!", "", "-leading", "Upper"):
            with self.subTest(bad=bad), self.assertRaises(ScenarioError):
                scaffold(bad, self.root)

    def test_a_service_name_that_cannot_prefix_a_tool_is_refused(self) -> None:
        """Tool names are `<service>_<verb>`, so the name has to be usable there."""
        with self.assertRaises(ScenarioError):
            scaffold("my-probe", self.root, service="not a name")


class GeneratedScenarioRunsTests(unittest.TestCase):
    """
    The scaffold's entire claim is that it runs before you have edited
    anything, and that its second subject fails. Asserting the files exist
    would not catch a scaffold that generates a scenario nothing can satisfy —
    the first draft of this one did exactly that, twice.
    """

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)

    def _run(self, scenario_id: str, subject: str, service: bool) -> dict:
        directory = self.root / scenario_id
        output = self.root / "runs" / subject
        command = [
            sys.executable,
            "-m",
            "beacon",
            "run",
            str(directory / "scenario.json"),
            "--adapter",
            "command",
            "--command",
            f"{sys.executable} {directory / 'subjects' / subject}",
            "--output",
            str(output),
        ]
        if service:
            command += ["--service-module", str(directory / "service.py")]
        subprocess.run(command, cwd=REPO_ROOT, capture_output=True, check=False)
        bundles = list(output.glob("*/evidence.json"))
        self.assertEqual(len(bundles), 1, "the run wrote no evidence bundle")
        return json.loads(bundles[0].read_text(encoding="utf-8"))

    def _check_pair(self, scenario_id: str, service: str | None) -> None:
        scaffold(scenario_id, self.root, service=service)
        passing = self._run(scenario_id, "compliant.py", service is not None)
        self.assertEqual(passing["result"], "PASS", passing["subject"].get("execution"))

        failing = self._run(scenario_id, "violating.py", service is not None)
        self.assertEqual(failing["result"], "FAIL")

        # Exactly one assertion, and a different one each time would mean the
        # violating subject is broken rather than non-compliant.
        broken = [
            item["id"] for item in failing["assertions"] if not item["passed"]
        ]
        self.assertEqual(len(broken), 1, f"expected one failure, got {broken}")

    def test_the_black_box_scaffold_passes_then_fails(self) -> None:
        self._check_pair("scaffold-probe", None)

    def test_the_service_scaffold_passes_then_fails(self) -> None:
        self._check_pair("scaffold-service-probe", "notes")




class GeneratedSourceCompilesTests(unittest.TestCase):
    """
    `project-beacon init` writes the scaffold's own location into the docstrings of
    the subjects it generates. On Windows that is a backslash path, so
    `C:\\Users\\...` puts `\\U` inside a string literal where Python reads a
    truncated unicode escape. Every subject generated on Windows was a syntax
    error, and the harness reported it as the subject failing to start.

    Reproduced on any platform by scaffolding into a directory whose *name*
    contains the sequence, so this stays honest without a Windows runner.
    """

    AWKWARD = (r"C:\Users", r"D:\new", r"E:\x123", r"F:\Nope", r"G:\Ugly")

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_generated_subjects_compile_from_a_backslash_path(self) -> None:
        for index, name in enumerate(self.AWKWARD):
            target = self.root / f"case{index}" / name
            target.mkdir(parents=True)
            scaffold("probe", target)
            for path in sorted((target / "probe" / "subjects").glob("*.py")):
                with self.subTest(directory=name, subject=path.name):
                    try:
                        compile(path.read_text(encoding="utf-8"), str(path), "exec")
                    except SyntaxError as error:
                        self.fail(f"{path.name} does not compile: {error}")

    def test_the_generated_service_compiles_too(self) -> None:
        target = self.root / r"C:\Users\runner"
        target.mkdir(parents=True)
        scaffold("probe", target, service="notes")
        service = target / "probe" / "service.py"
        compile(service.read_text(encoding="utf-8"), str(service), "exec")

    def test_no_embedded_path_carries_a_backslash(self) -> None:
        """
        The property behind the fix. Checked on the lines that quote a path
        rather than the whole file, since a generated shell example ends its
        lines with a legitimate backslash continuation.
        """
        target = self.root / r"C:\Users"
        target.mkdir(parents=True)
        scaffold("probe", target)
        for path in (target / "probe").rglob("*"):
            if path.suffix not in {".py", ".md"}:
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if "probe/scenario.json" in line or "probe/subjects" in line:
                    with self.subTest(file=path.name, line=line.strip()[:60]):
                        self.assertNotIn("\\", line.rstrip("\\"))


if __name__ == "__main__":
    unittest.main()
