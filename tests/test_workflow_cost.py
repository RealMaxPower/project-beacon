from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))

# Billed multipliers on private repositories. Public repositories are free,
# which is exactly why this only matters until this one is published.
RUNNER_COST = {"ubuntu": 1, "windows": 2, "macos": 10}


def _trigger_block(text: str) -> str:
    """The `on:` section, up to the next top-level key."""
    match = re.search(r"^on:\n(.*?)(?=^\w)", text, re.M | re.S)
    return match.group(1) if match else ""


def _uncommented(block: str) -> list[str]:
    return [
        line for line in block.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


class WorkflowCostTests(unittest.TestCase):
    """
    This repository is private, so Actions minutes are billed, and the runner
    multipliers are uneven: Linux 1x, Windows 2x, macOS 10x.

    The CI matrix — three operating systems by three Python versions — cost
    about 104 billed minutes per push. Nineteen pushes against the free
    allowance, three quarters of it macOS, discovered by pushing twice and
    reading the bill. Every workflow is therefore `workflow_dispatch` only.

    Turning them off through the API instead would have worked and left no
    trace in the repository: invisible state, not inherited by a clone or a
    fork, and re-enabled by one click with nothing to explain the cost. This
    keeps the decision in git, where changing it is a diff somebody reviews.
    """

    def test_there_are_workflows_to_check(self) -> None:
        """A passing suite because the glob found nothing proves nothing."""
        self.assertTrue(WORKFLOWS, "no workflow files found")

    def test_no_workflow_runs_without_someone_asking(self) -> None:
        for path in WORKFLOWS:
            block = _trigger_block(path.read_text(encoding="utf-8"))
            with self.subTest(workflow=path.name):
                self.assertTrue(block.strip(), "no `on:` block found")
                live = _uncommented(block)
                self.assertTrue(live, "no active trigger at all")
                for trigger in ("push:", "pull_request:", "schedule:"):
                    self.assertFalse(
                        any(line.strip().startswith(trigger) for line in live),
                        f"{trigger} is active — every push would be billed. "
                        f"Comment it out until the repository is public.",
                    )

    def test_every_workflow_can_still_be_started_by_hand(self) -> None:
        """Zero cost must not mean zero ability to run it before a release."""
        for path in WORKFLOWS:
            block = _trigger_block(path.read_text(encoding="utf-8"))
            with self.subTest(workflow=path.name):
                self.assertTrue(
                    any(
                        line.strip().startswith("workflow_dispatch:")
                        for line in _uncommented(block)
                    ),
                    "no workflow_dispatch, so this cannot be run at all",
                )

    def test_the_restoration_path_is_written_down(self) -> None:
        """
        A commented-out trigger with no explanation reads as debris, and the
        next person deletes it or uncomments it without knowing what it costs.
        """
        for path in WORKFLOWS:
            text = path.read_text(encoding="utf-8")
            with self.subTest(workflow=path.name):
                self.assertIn("WHEN THE REPOSITORY GOES PUBLIC", text)
                self.assertIn("# push:", text, "no trigger left to restore")

    def test_the_expensive_runners_are_still_named_somewhere(self) -> None:
        """
        The matrix is kept, not deleted — it is right for a public repository
        and free there. This guards against someone 'fixing' the cost by
        throwing away the coverage instead of the trigger.
        """
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        for runner in ("ubuntu-latest", "windows-latest", "macos-latest"):
            with self.subTest(runner=runner):
                self.assertIn(runner, ci)

    def test_the_cost_note_states_the_multipliers(self) -> None:
        ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        for fragment in ("Linux 1x", "Windows 2x", "macOS 10x"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, ci)


class LocalEquivalentTests(unittest.TestCase):
    """
    With CI off, the local commands are the only checks that run. They have to
    be written down somewhere a contributor will look.
    """

    def test_contributing_gives_the_commands_that_replace_ci(self) -> None:
        text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertIn("unittest discover -s tests", text)
        self.assertIn("examples/subjects/run_suite.py", text)

    def test_contributing_says_what_the_local_run_does_not_cover(self) -> None:
        """
        The honest gap: no operating-system matrix. Saying "run these two
        commands" without it would imply a coverage that is not there.
        """
        text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertIn("operating-system\nmatrix", text.replace("  ", " "))


if __name__ == "__main__":
    unittest.main()
