from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRIBUTING = ROOT / "CONTRIBUTING.md"

POLICY_START = "Close the gap between the rules and what enforces them"
"""
The first commit required to carry a sign-off, and every commit after it.

Named by commit *subject* rather than by hash so the check survives a rebase,
and so a reader can find the boundary without consulting the test. It is the
commit that introduced this file, which is the earliest one that could
honestly be held to a rule nothing had been checking.

A history that does not contain it is a history that began *after* the policy,
so every commit in it is in scope. That case is not hypothetical: this project
was published as a squashed tree, and for that history the boundary subject
does not exist. Skipping there — which is what this check used to do — left the
rule with no enforcement at all in the only repository anyone can clone.
"""


LOG_FORMAT = "%H%x1f%P%x1f%s%x1f%(trailers:key=Signed-off-by,valueonly)%x1e"
"""
One record per commit: hash, parents, subject, sign-off trailer.

`%P` is here so merge commits can be told apart by parent count rather than by
matching their subject line, which anyone could write by hand.
"""


def unsigned_commits(log: str) -> list[str]:
    """
    The in-scope commits in `log` that carry no sign-off.

    Split out from the test so the merge-commit rule below can be exercised
    against a log this file writes, rather than only against whatever history
    the checkout happens to have. A rule that can only be tested by being in the
    right repository on the right day is not being tested.

    **Merge commits are skipped, and that is not a loosening.** GitHub's DCO app
    skips them for the same reason: nobody writes a merge commit, so nobody can
    certify one. A `pull_request` run does not check out the contributor's
    commit — it checks out the ephemeral merge commit GitHub synthesises for the
    pull request, whose subject is `Merge <head> into <base>` and whose author is
    GitHub. Holding that to the policy failed every pull request ever opened,
    including ones whose own commits were signed correctly, and the failure named
    a commit its author could neither sign nor remove.

    It stayed hidden because CI had only ever run on pushes to `main`, which
    check out a real commit. The first pull request this repository received hit
    it immediately, on all nine matrix legs at once.
    """
    commits = [
        entry.strip("\n").split("\x1f")
        for entry in log.split("\x1e")
        if entry.strip()
    ]
    commits = [record for record in commits if len(record[1].split()) <= 1]
    subjects = [subject for _, _, subject, _ in commits]

    # `git log` is newest first, so the boundary and everything before it in
    # this list is the boundary and everything after it in time. Absent a
    # boundary the whole history is in scope — see POLICY_START. The one thing
    # this must never do is decline to answer, which is how the rule came to be
    # enforced nowhere.
    boundary = next(
        (
            index
            for index, subject in enumerate(subjects)
            if subject.startswith(POLICY_START)
        ),
        len(commits) - 1,
    )
    return [
        f"{sha[:9]} {subject}"
        for sha, _, subject, trailer in commits[: boundary + 1]
        if not re.fullmatch(r".+ <.+@.+>", trailer.strip())
    ]


def _git(*args: str) -> str | None:
    """Run git, or return None where there is no repository to ask."""
    try:
        result = subprocess.run(
            ("git", *args),
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - defensive
        return None
    if result.returncode != 0:
        return None
    return result.stdout


class SignOffPolicyTests(unittest.TestCase):
    """
    `CONTRIBUTING.md` asks contributors to sign off, and no commit did.

    That is the project's own failure mode turned inward: a rule stated and not
    kept, with nothing checking. Rewriting the existing history was not the
    answer — a sign-off added retroactively by someone else certifies nothing —
    so the policy now names the commit it starts from, and this asserts the two
    halves stay together.
    """

    def test_the_requirement_is_still_stated(self) -> None:
        text = CONTRIBUTING.read_text(encoding="utf-8")
        self.assertIn("git commit -s", text)
        self.assertIn("Developer Certificate of Origin", text)

    def test_the_requirement_says_when_it_starts_applying(self) -> None:
        """
        Without this the rule reads as covering the whole history, which would
        be the same overstatement in a new place.
        """
        text = CONTRIBUTING.read_text(encoding="utf-8")
        self.assertRegex(text, r"applies from the commit .* onward")
        self.assertIn("Any commit\nbefore it is unsigned", text)
        # And that it says what happens where there is no boundary to apply
        # from, which is the shape of the published history.
        self.assertIn("began after the policy, so the walk covers all of it", text)

    def test_commits_since_the_policy_are_signed_off(self) -> None:
        """
        The check that gives the rule teeth. Skipped rather than failed where
        there is no git history to read — an unpacked sdist has none, and a
        test that cannot see the evidence must not report a verdict on it.
        """
        # `%(trailers:...)` rather than `%b` and a regex over it. The two
        # disagree, and the disagreement is the whole point: a `Signed-off-by:`
        # line with prose after it still matches a line-anchored regex, and git
        # — like GitHub's DCO app — does not see it as a trailer at all, because
        # a trailer block ends at the first paragraph that is not one. This
        # check used to pass a commit that a real DCO gate would reject, which
        # is worse than not checking: it certifies the wrong thing. Found by
        # amending a message and appending a paragraph below the sign-off.
        log = _git("log", f"--format={LOG_FORMAT}")
        if not log:
            self.skipTest("no git history available")

        # A shallow clone is not a short history, it is a history with the far
        # end cut off — `git log` returns the tip and stops, and `%P` on the
        # boundary commit is empty because the parents are not there to name.
        # Walking it would report "no unsigned commits" after reading one, which
        # is the difference between passing and having checked. `fetch-depth: 0`
        # in CI keeps this from being reached there; the guard below asserts it.
        if (_git("rev-parse", "--is-shallow-repository") or "").strip() == "true":
            self.skipTest(
                "shallow checkout: the walk cannot reach the policy boundary, "
                "and a verdict from a history this cannot see would be invented"
            )

        unsigned = unsigned_commits(log)
        self.assertEqual(
            unsigned,
            [],
            "commits after the policy took effect are missing a sign-off:\n"
            + "\n".join(unsigned),
        )

    @staticmethod
    def _record(sha: str, parents: str, subject: str, trailer: str = "") -> str:
        return f"{sha}\x1f{parents}\x1f{subject}\x1f{trailer}\x1e"

    SIGNED = "A Contributor <contributor@example.com>"

    def _boundary(self) -> str:
        """The commit the policy starts from, signed, to close the walk."""
        return self._record(
            "b" * 40, "c" * 40, f"{POLICY_START} everywhere", self.SIGNED
        )

    def test_the_merge_commit_github_writes_for_a_pull_request_is_not_held_to_it(
        self,
    ) -> None:
        """
        The check ran only on pushes to `main` until this repository received a
        pull request, and then failed all nine matrix legs on a commit GitHub
        had written itself. A contributor can neither sign that commit nor
        remove it, so failing them for it asks for something nobody can give.
        """
        log = (
            self._record("a" * 40, f"{'b' * 40} {'d' * 40}", "Merge bbb into ddd")
            + self._boundary()
        )
        self.assertEqual(unsigned_commits(log), [])

    def test_an_unsigned_ordinary_commit_is_still_caught(self) -> None:
        """
        Rules out the opposite error, and it is the one that matters: a filter
        wide enough to swallow the merge commit could swallow everything, and
        the check would pass forever while certifying nothing. That is the exact
        failure this file exists to end, so skipping merges has to be narrower
        than "stop looking".
        """
        log = (
            self._record("a" * 40, "b" * 40, "A commit somebody actually wrote")
            + self._boundary()
        )
        self.assertEqual(
            unsigned_commits(log),
            ["aaaaaaaaa A commit somebody actually wrote"],
        )

    def test_a_signed_ordinary_commit_passes(self) -> None:
        """The third leg: the check must also say yes to what is correct."""
        log = (
            self._record("a" * 40, "b" * 40, "A signed commit", self.SIGNED)
            + self._boundary()
        )
        self.assertEqual(unsigned_commits(log), [])

    CI = ROOT / ".github" / "workflows" / "ci.yml"

    def test_ci_checks_out_the_history_this_walk_needs(self) -> None:
        """
        The rule and the thing that enforces it, kept together — which is what
        the rest of this file is for.

        `actions/checkout` fetches depth 1 unless told otherwise, and under that
        default this check read one commit and reported no unsigned commits in
        the whole history. It passed every run on `main` that way, having never
        reached the boundary. The skip above keeps it from inventing a verdict;
        this keeps CI from being the place where it never gets to answer.

        Asserted on every job that runs the suite, not on the file as a whole,
        because a `fetch-depth: 0` on the site job would satisfy a laxer check
        while the walk stayed blind.
        """
        text = self.CI.read_text(encoding="utf-8")
        _, _, body = text.partition("\njobs:\n")
        self.assertTrue(body, "ci.yml has no jobs block to read")
        jobs = [job for job in re.split(r"\n  (?=[A-Za-z][\w-]*:\n)", body) if job.strip()]

        def runs_the_suite(job: str) -> bool:
            # Only what CI actually executes. The header of this file quotes
            # the same command in a comment, and a comment runs nothing.
            return any(
                "unittest discover" in line and not line.lstrip().startswith("#")
                for line in job.splitlines()
            )

        running = [job for job in jobs if runs_the_suite(job)]
        self.assertTrue(running, "no job in ci.yml runs the suite any more")
        for job in running:
            name = job.strip().split("\n", 1)[0].rstrip(":")
            with self.subTest(job=name):
                self.assertRegex(
                    job,
                    r"actions/checkout@[^\n]*\n\s*with:\n\s*fetch-depth:\s*0",
                    f"{name} runs the suite without full history, so the "
                    "sign-off walk passes there without reading anything",
                )


class CodeOfConductTests(unittest.TestCase):
    """
    A code of conduct is a rule, and this project's whole argument is that a
    rule stated without something behind it is worse than no rule.

    The two ways this one fails quietly are both checked here: the template's
    `[INSERT CONTACT METHOD]` surviving into the published file, and the file
    existing with nothing linking to it.
    """

    CONDUCT = ROOT / "CODE_OF_CONDUCT.md"

    def test_it_exists(self) -> None:
        self.assertTrue(self.CONDUCT.is_file())

    def test_the_reporting_placeholder_was_filled_in(self) -> None:
        """
        The template ships `[INSERT CONTACT METHOD]`, which reads as a complete
        document to anyone skimming and names no channel at all.
        """
        self.assertNotIn("[INSERT CONTACT METHOD]", self.CONDUCT.read_text(encoding="utf-8"))

    def test_it_names_an_address_that_can_receive_mail(self) -> None:
        """
        A GitHub `users.noreply` address accepts no mail, so naming one would
        be a reporting channel that silently discards reports.
        """
        text = self.CONDUCT.read_text(encoding="utf-8")
        self.assertRegex(text, r"[\w.+-]+@[\w-]+\.[\w.]+")
        self.assertNotIn("users.noreply.github.com", text)

    def test_contributing_links_to_it(self) -> None:
        """GitHub does not link the two, so a file nothing points at is unread."""
        self.assertIn("CODE_OF_CONDUCT.md", CONTRIBUTING.read_text(encoding="utf-8"))

    def test_it_admits_the_enforcement_body_is_one_person(self) -> None:
        """
        The template says "community leaders", plural, and describes an appeals
        path through them. There is one maintainer. Shipping the plural
        unqualified would describe a structure that does not exist — the same
        overstatement the rest of this file exists to prevent.
        """
        text = self.CONDUCT.read_text(encoding="utf-8")
        self.assertIn("only\nmaintainer", text)
        self.assertIn("report-abuse", text)


if __name__ == "__main__":
    unittest.main()
