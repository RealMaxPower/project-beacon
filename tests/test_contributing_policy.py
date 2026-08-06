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
"""


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
        self.assertIn("Every\ncommit before it is unsigned", text)

    def test_commits_since_the_policy_are_signed_off(self) -> None:
        """
        The check that gives the rule teeth. Skipped rather than failed where
        there is no git history to read — an unpacked sdist has none, and a
        test that cannot see the evidence must not report a verdict on it.
        """
        log = _git("log", "--format=%H%x1f%s%x1f%b%x1e")
        if not log:
            self.skipTest("no git history available")

        commits = [
            entry.strip("\n").split("\x1f")
            for entry in log.split("\x1e")
            if entry.strip()
        ]
        subjects = [subject for _, subject, _ in commits]
        if not any(s.startswith(POLICY_START) for s in subjects):
            self.skipTest("policy boundary commit is not in this history")

        # `git log` is newest first, so the boundary and everything before it
        # in this list is the boundary and everything after it in time.
        boundary = next(
            index
            for index, subject in enumerate(subjects)
            if subject.startswith(POLICY_START)
        )
        unsigned = [
            f"{sha[:9]} {subject}"
            for sha, subject, body in commits[: boundary + 1]
            if not re.search(r"^Signed-off-by: .+ <.+>$", body, re.M)
        ]
        self.assertEqual(
            unsigned,
            [],
            "commits after the policy took effect are missing a sign-off:\n"
            + "\n".join(unsigned),
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
