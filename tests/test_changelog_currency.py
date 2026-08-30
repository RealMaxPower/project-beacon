from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"

VERSION_HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\]", re.M)
UNRELEASED_HEADING = "## [Unreleased]"


def unreleased_account(text: str, tags: set[str]) -> str:
    """
    Everything said about work that has not shipped yet.

    That is `## [Unreleased]` **plus any version section with no tag**, because
    cutting a release renames the first into the second and the tag arrives in a
    later commit. Between those two moments `## [Unreleased]` is empty and the
    account lives under a version heading — which is a described change, not an
    undescribed one.

    This was found by the first release after the check was written: 0.3.1's
    section was complete, `[Unreleased]` had just been emptied into it, and the
    check called the work undescribed. `tools/check_release_drift.py` was given
    a grace window for the same window; this had none. A check that fires during
    the ordinary way of doing the thing is one people learn to route around.
    """
    accounts = [unreleased_body(text)]
    for version in VERSION_HEADING.findall(text):
        if f"v{version}" not in tags:
            accounts.append(_section_body(text, f"## [{version}]"))
    return "\n".join(part for part in accounts if part).strip()


def unreleased_body(text: str) -> str:
    """
    What has actually been said under `## [Unreleased]`, up to the next version
    heading.

    Section headings are stripped before the answer is given, so a bare
    `### Added` with nothing beneath it reads as empty. That is not
    pedantry — it is the whole failure mode. A check satisfied by a heading is
    satisfied by typing four characters, and the point is an account of what
    changed, not the shape of one. Found by the test below, which asserted the
    opposite of what the first version of this function did.

    Bounded at the next version heading, or a released entry would satisfy the
    check forever.
    """
    return _section_body(text, UNRELEASED_HEADING)


def _section_body(text: str, heading: str) -> str:
    """The content under `heading`, up to the next version heading."""
    start = text.find(heading)
    if start == -1:
        return ""
    rest = text[start + len(heading) :]
    match = VERSION_HEADING.search(rest)
    body = rest[: match.start()] if match else rest
    said = [
        line for line in body.splitlines() if line.strip() and not line.startswith("#")
    ]
    return "\n".join(said).strip()


def undescribed(unreleased: str, commits: list[tuple[str, list[str]]]) -> list[str]:
    """
    Commits that changed the package since the last release with nothing said
    about them.

    Each commit is `(subject, paths)`. Pure, and takes every fact as an
    argument, so the cases below hold on any day in any checkout — the same
    reason `unsigned_commits` in `test_contributing_policy.py` is shaped this
    way.

    **Only commits touching `beacon/` count.** A changelog entry for a workflow
    file or a test helper is noise, and a check that demanded one would be red
    after every piece of housekeeping — which is how a check gets ignored, and
    then deleted. The package is what a reader installs, so the package is what
    the changelog owes them an account of.

    This exists because `## [Unreleased]` sat empty with two merged pull
    requests past the tag, one of which changed observable behaviour: every
    probe began sending a `DELETE`, and a flag's default moved. Nothing could
    say so. It is the same shape as the release that was declared and never
    published — a claim contradicted by evidence already in the repository —
    and it appeared the day after the guard for that one was written.
    """
    if unreleased:
        return []
    return [
        subject
        for subject, paths in commits
        if any(path.startswith("beacon/") for path in paths)
    ]


def _git(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ("git", *args), cwd=ROOT, capture_output=True, text=True,
            timeout=30, check=False,
        )
    except (OSError, subprocess.SubprocessError):  # pragma: no cover - defensive
        return None
    return result.stdout if result.returncode == 0 else None


def _commits_since_last_release() -> list[tuple[str, list[str]]] | None:
    """`(subject, paths)` for each commit after the newest version tag."""
    tags = _git("tag", "-l", "v*", "--sort=-v:refname")
    if not tags or not tags.strip():
        return None
    newest = tags.split()[0]
    log = _git("log", f"{newest}..HEAD", "--format=%x1e%s", "--name-only")
    if log is None:
        return None
    commits: list[tuple[str, list[str]]] = []
    for record in log.split("\x1e"):
        lines = [line for line in record.strip().splitlines() if line.strip()]
        if lines:
            commits.append((lines[0], lines[1:]))
    return commits


class ChangelogCurrencyTests(unittest.TestCase):
    """
    `## [Unreleased]` empty is a claim: nothing has changed since the release.

    It is checkable, unlike the version-to-PyPI question `tools/check_release_drift.py`
    answers, because both halves are in the repository — so this is a test
    rather than a scheduled job.
    """

    def test_a_package_change_since_the_release_is_described(self) -> None:
        commits = _commits_since_last_release()
        if commits is None:
            self.skipTest("no tags or no git history to read")
        tags = set((_git("tag", "-l") or "").split())
        missing = undescribed(
            unreleased_account(CHANGELOG.read_text(encoding="utf-8"), tags), commits
        )
        self.assertEqual(
            missing,
            [],
            "these commits changed beacon/ since the last release and "
            "## [Unreleased] is empty:\n" + "\n".join(missing),
        )

    def test_an_empty_unreleased_is_fine_when_nothing_changed(self) -> None:
        """The state right after a release, and by far the common one."""
        self.assertEqual(undescribed("", []), [])

    def test_housekeeping_alone_needs_no_entry(self) -> None:
        """
        The case that keeps this usable. A workflow file or a test helper is
        not something a reader installs, and demanding an entry for one would
        make the check red after every piece of maintenance.
        """
        commits = [
            ("Pin the actions", [".github/workflows/ci.yml"]),
            ("Widen a fixture", ["tests/test_runner.py"]),
        ]
        self.assertEqual(undescribed("", commits), [])

    def test_a_package_change_with_nothing_said_is_caught(self) -> None:
        commits = [("Change how a probe closes", ["beacon/protocols/mcp_http.py"])]
        self.assertEqual(undescribed("", commits), ["Change how a probe closes"])

    def test_saying_something_satisfies_it(self) -> None:
        """
        Deliberately not a judgement about the prose. This checks that an
        account was given, not that it is a good one — a test that graded
        wording would be enforcing taste, and would be gamed by a placeholder
        either way.
        """
        commits = [("Change how a probe closes", ["beacon/protocols/mcp_http.py"])]
        self.assertEqual(undescribed("### Changed\n\n- It closes.", commits), [])

    def test_a_cut_but_untagged_release_counts_as_an_account(self) -> None:
        """
        The release-prep window, and the case that made this rule wrong once.

        Cutting a release renames `[Unreleased]` to a version heading, and the
        tag lands in a later commit. In between, `[Unreleased]` is empty and the
        account sits under `## [0.3.1]` — described work, not undescribed. The
        drift check was given a grace window for this same gap; this had none,
        and failed on the first release after it was written.
        """
        text = (
            "## [Unreleased]\n\n## [0.3.1] — 2026-08-30\n\n"
            "### Fixed\n\n- a real thing\n\n## [0.3.0] — 2026-08-30\n\n- older\n"
        )
        # v0.3.1 not tagged yet, v0.3.0 is
        self.assertIn("a real thing", unreleased_account(text, {"v0.3.0"}))
        # and once it is tagged, that section stops counting as unreleased
        self.assertEqual(unreleased_account(text, {"v0.3.0", "v0.3.1"}), "")

    def test_a_released_section_never_satisfies_it(self) -> None:
        """
        Otherwise the newest shipped entry would answer for every future change
        and the check would pass forever.
        """
        text = "## [Unreleased]\n\n## [0.3.0] — 2026-08-30\n\n- shipped already\n"
        account = unreleased_account(text, {"v0.3.0"})
        self.assertEqual(account, "")
        commits = [("Change the package", ["beacon/runner.py"])]
        self.assertEqual(undescribed(account, commits), ["Change the package"])

    def test_the_unreleased_section_is_found_and_bounded(self) -> None:
        """
        The parse the rule rests on: everything up to the next version heading
        and nothing after it, or a released entry would satisfy the check
        forever.
        """
        text = (
            "# Changelog\n\n## [Unreleased]\n\n### Added\n\n- a thing\n\n"
            "## [0.3.0] — 2026-08-30\n\n- an older thing\n"
        )
        body = unreleased_body(text)
        self.assertIn("a thing", body)
        self.assertNotIn("older thing", body)
        self.assertEqual(unreleased_body(text.replace("- a thing\n", "")), "")
