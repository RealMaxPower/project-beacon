from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS_DIR = ROOT / ".github" / "workflows"
WORKFLOWS = sorted(WORKFLOWS_DIR.glob("*.yml"))

# What each workflow may be started by. Default-deny: a file that is not in
# this table fails rather than inheriting a permissive default, because the
# failure this guards against is a new workflow arriving with a trigger nobody
# thought about.
ALLOWED_TRIGGERS = {
    "ci.yml": {"workflow_dispatch", "push", "pull_request"},
    "release.yml": {"workflow_dispatch", "push"},
    "conformance.yml": {"workflow_dispatch"},
}

# Triggers no workflow here may carry. `pull_request_target` runs the base
# branch's workflow, with a token that can write, against a fork's code. It is
# the standard public-repository escalation, and it is a risk that did not
# exist while nobody outside could open a pull request — so it is forbidden
# here before anyone reaches for it, rather than after.
NEVER = frozenset(
    {"pull_request_target", "workflow_run", "repository_dispatch", "issue_comment"}
)


def _trigger_block(text: str) -> str:
    """The `on:` section, up to the next top-level key."""
    match = re.search(r"^on:\n(.*?)(?=^\w)", text, re.M | re.S)
    return match.group(1) if match else ""


def _uncommented(block: str) -> list[str]:
    return [
        line for line in block.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def _active_triggers(block: str) -> set[str]:
    """
    The trigger names in an `on:` block, ignoring each one's settings.

    Indentation is the discriminator: a trigger sits at two spaces, and
    everything configuring it is deeper. That keeps `branches:` under a `push:`
    from being counted as a trigger of its own.
    """
    return {
        line.strip().rstrip(":")
        for line in _uncommented(block)
        if line.startswith("  ")
        and not line.startswith("   ")
        and line.rstrip().endswith(":")
    }


class WorkflowTriggerTests(unittest.TestCase):
    """
    What may start a workflow, and what may never.

    Every workflow here was `workflow_dispatch` only for the first months of
    this project, because Actions minutes are billed on a private repository
    and the matrix measured at ~104 billed minutes per push. That reason
    expired on publication and the triggers came back.

    What replaced it is not "anything goes". One workflow calls other people's
    running services and is still manual for that reason alone. The
    operating-system matrix is still the thing that catches Windows defects.
    And `pull_request_target` only became dangerous the day a stranger could
    open a pull request, which is the day this file started forbidding it.
    """

    def test_there_are_workflows_to_check(self) -> None:
        """A passing suite because the glob found nothing proves nothing."""
        self.assertTrue(WORKFLOWS, "no workflow files found")

    def test_every_workflow_is_classified(self) -> None:
        """
        A new workflow must be a decision, not an inheritance.

        The table above is default-deny, so adding a CodeQL or a deploy
        workflow fails here until someone writes down what may start it — which
        is the moment to notice it would run on every fork's pull request.
        """
        self.assertEqual(sorted(p.name for p in WORKFLOWS), sorted(ALLOWED_TRIGGERS))

    def test_no_workflow_carries_a_forbidden_trigger(self) -> None:
        for path in WORKFLOWS:
            triggers = _active_triggers(_trigger_block(path.read_text(encoding="utf-8")))
            with self.subTest(workflow=path.name):
                self.assertEqual(
                    triggers & NEVER,
                    set(),
                    "runs fork-authored code with the base branch's token",
                )

    def test_no_workflow_is_started_by_more_than_it_was_signed_up_for(self) -> None:
        for path in WORKFLOWS:
            block = _trigger_block(path.read_text(encoding="utf-8"))
            triggers = _active_triggers(block)
            with self.subTest(workflow=path.name):
                self.assertTrue(triggers, "no active trigger at all")
                self.assertLessEqual(triggers, ALLOWED_TRIGGERS[path.name])

    def test_every_workflow_can_still_be_started_by_hand(self) -> None:
        """Automatic runs must not cost the ability to run one before a release."""
        for path in WORKFLOWS:
            triggers = _active_triggers(_trigger_block(path.read_text(encoding="utf-8")))
            with self.subTest(workflow=path.name):
                self.assertIn("workflow_dispatch", triggers)


class ThirdPartyTrafficTests(unittest.TestCase):
    """
    The conformance sweep stays manual, and the reason is no longer cost.

    It drives third-party MCP servers and hosted agents belonging to people who
    did not ask to be measured. Free minutes changed what a weekly cron costs
    us and changed nothing about what it costs them. This was written down as
    the second of two reasons while the first was still true. It is now the
    only one, and unlike the first it does not expire.
    """

    CONFORMANCE = WORKFLOWS_DIR / "conformance.yml"

    def test_a_person_starts_it_or_nothing_does(self) -> None:
        block = _trigger_block(self.CONFORMANCE.read_text(encoding="utf-8"))
        self.assertEqual(_active_triggers(block), {"workflow_dispatch"})

    def test_no_commented_out_trigger_waits_to_be_restored(self) -> None:
        """
        A `# schedule:` under "uncomment when the repository is public" is an
        instruction, and the repository is public. The block was deleted rather
        than left behind, so the next person has to add a trigger deliberately
        and meets the paragraph explaining why not on the way.
        """
        block = _trigger_block(self.CONFORMANCE.read_text(encoding="utf-8"))
        for trigger in ("schedule:", "push:", "pull_request:"):
            with self.subTest(trigger=trigger):
                self.assertNotIn(f"# {trigger}", block)

    def test_the_file_says_whose_services_it_calls(self) -> None:
        """The reason lives beside the setting, or the setting reads as debris."""
        self.assertIn(
            "other people's running services",
            self.CONFORMANCE.read_text(encoding="utf-8"),
        )


class ReleaseTriggerTests(unittest.TestCase):
    """
    `release.yml` publishes to PyPI, so its automatic trigger is the one with
    teeth. A `push:` without a `tags:` filter would build every commit on main
    inside a job that holds a PyPI id-token.
    """

    RELEASE = WORKFLOWS_DIR / "release.yml"

    def test_the_push_trigger_is_restricted_to_tags(self) -> None:
        block = _trigger_block(self.RELEASE.read_text(encoding="utf-8"))
        self.assertIn("push", _active_triggers(block))
        push = re.search(r"^  push:\n((?:    .*\n)+)", block, re.M)
        self.assertIsNotNone(push, "the push trigger moved; repoint this guard")
        self.assertIn("tags:", push.group(1))
        self.assertNotIn("branches:", push.group(1))

    def test_publishing_is_still_gated_on_the_tag_itself(self) -> None:
        """Two independent gates, because the trigger is one edit from wrong."""
        self.assertIn(
            "if: startsWith(github.ref, 'refs/tags/v') || inputs.publish",
            self.RELEASE.read_text(encoding="utf-8"),
        )


class MatrixCoverageTests(unittest.TestCase):
    """
    The operating-system matrix, kept.

    It survived the whole manual period unrun because it is right for a public
    repository, where it is free. Deleting a runner is the tempting way to make
    CI faster, and the one that throws away the coverage instead of the cost.
    """

    CI = WORKFLOWS_DIR / "ci.yml"

    def test_all_three_operating_systems_are_still_in_the_matrix(self) -> None:
        ci = self.CI.read_text(encoding="utf-8")
        for runner in ("ubuntu-latest", "windows-latest", "macos-latest"):
            with self.subTest(runner=runner):
                self.assertIn(runner, ci)

    def test_the_vertical_slice_still_runs_on_windows(self) -> None:
        """
        The only job that exercises the CLI's `shlex`-based `--command`
        parsing, where a backslash path is eaten as an escape. The unit tests
        never reach it: they launch subjects with `sys.executable`.
        """
        ci = self.CI.read_text(encoding="utf-8")
        slice_job = ci[ci.index("vertical-slice:"):]
        self.assertIn("windows-latest", slice_job[: slice_job.index("steps:")])


class LocalEquivalentTests(unittest.TestCase):
    """
    CI runs on a pull request now, which makes the local commands a first pass
    rather than the only pass. They still have to be written down: they are the
    fast answer while you are working, and the two things the pull-request
    template asks you to tick.
    """

    def test_contributing_gives_the_commands_ci_will_run(self) -> None:
        text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        self.assertIn("unittest discover -s tests", text)
        self.assertIn("examples/subjects/run_suite.py", text)

    def test_contributing_says_what_the_local_run_does_not_cover(self) -> None:
        """
        Whitespace-normalised, unlike the check this replaces, which pinned the
        line break between "operating-system" and "matrix" and would have
        failed on a re-wrap of a paragraph nobody meant to change.
        """
        text = " ".join((ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8").split())
        self.assertIn("operating-system matrix", text)


if __name__ == "__main__":
    unittest.main()
