from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "check_release_drift.py"


def _load():
    """
    Import the checker by path.

    `tools/` is not a package and is not shipped in the sdist, so this skips
    rather than fails where the script is absent — the same rule the rest of
    the suite follows for files a distribution does not carry.
    """
    spec = importlib.util.spec_from_file_location("check_release_drift", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(SCRIPT.is_file(), "tools/ is not shipped in the sdist")
class ReleaseDriftTests(unittest.TestCase):
    """
    The check that would have caught 0.3.0 sitting unpublished for a week.

    `pyproject.toml` announcing a version is a claim; a tag and a PyPI release
    are the evidence for it. Nothing compared the three, because the version is
    bumped in one commit and tagged in another — so a test demanding a tag
    would be red through every release — and because the suite is hermetic and
    cannot ask PyPI.

    `drift` takes every fact as an argument for exactly that reason: these
    cases hold on any day, with no network and no particular repository state.
    """

    def setUp(self) -> None:
        self.drift = _load().drift

    def test_a_version_declared_tagged_and_published_is_quiet(self) -> None:
        self.assertEqual(
            self.drift("0.3.0", {"v0.3.0"}, {"0.2.0", "0.3.0"}, 30), []
        )

    def test_the_gap_between_cutting_and_tagging_is_allowed(self) -> None:
        """
        A release is cut and then tagged, so an untagged version is normal for
        the minutes in between. A check that fired there would be red on every
        release, which is how a check gets ignored and then deleted.
        """
        self.assertEqual(self.drift("0.4.0", {"v0.3.0"}, {"0.3.0"}, 0.01), [])

    def test_an_untagged_version_is_reported_once_the_gap_outlives_it(self) -> None:
        """0.3.0 itself: declared, never tagged, a week gone by."""
        problems = self.drift("0.3.0", {"v0.2.0"}, {"0.2.0"}, 7)
        self.assertEqual(len(problems), 1)
        self.assertIn("no v0.3.0 tag exists", problems[0])

    def test_a_tag_with_no_release_is_reported(self) -> None:
        """
        The other way a release stalls: the tag is pushed, the workflow builds,
        and the publish job waits on a reviewer who never approves it.
        """
        problems = self.drift("0.3.0", {"v0.3.0"}, {"0.2.0"}, 7)
        self.assertEqual(len(problems), 1)
        self.assertIn("not on PyPI", problems[0])

    def test_an_unreachable_index_is_not_read_as_nothing_published(self) -> None:
        """
        The distinction this project exists to make. An index that could not be
        reached is "we could not tell", and reporting it as "nothing shipped"
        would be the same overstatement in a new place.
        """
        problems = self.drift("0.3.0", {"v0.3.0"}, set(), 7)
        self.assertEqual(len(problems), 1)
        self.assertIn("could not read", problems[0])
        self.assertNotIn("not on PyPI", problems[0])

    def test_a_missing_tag_is_reported_without_the_release_it_explains(self) -> None:
        """
        One finding, not two. A version with no tag also has no release, and
        saying both would report a single stall twice — the second line adding
        nothing a reader can act on separately.
        """
        problems = self.drift("0.3.0", set(), set(), 30)
        self.assertEqual(len(problems), 1)
        self.assertNotIn("PyPI", problems[0].replace("not on PyPI", ""))
