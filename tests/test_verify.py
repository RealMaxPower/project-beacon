from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from beacon.adapters import ReferenceInboxAdapter
from beacon.cli import main
from beacon.models import Scenario, canonical_digest
from beacon.runner import run_scenario


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios" / "inbox-briefing" / "scenario.json"
# Bound and skip-guarded below, because `MANIFEST.in` prunes the site out of
# the source distribution: an unguarded read here would make the sdist require
# a directory it does not ship. See `tests/test_packaging.py`.
SITE = ROOT / "site"


def _verify(path: Path) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(["verify", str(path)])
    return code, out.getvalue(), err.getvalue()


class VerifyTests(unittest.TestCase):
    """
    The digest was written down for eleven months before anything could check
    it, which made it decoration: a reader who wanted to act on it had to write
    the verifier first, and almost nobody does.

    What the command must not do is overstate what it found. A matching digest
    proves the file was not edited after the run. It does not prove the run
    happened, or happened here, and a reader who takes "VERIFIED" as either has
    been misled by the tool rather than by the bundle.
    """

    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.run_dir = Path(self.directory.name)
        outcome = run_scenario(
            Scenario.load(SCENARIO),
            ReferenceInboxAdapter(),
            output_dir=self.run_dir,
            run_id="verify",
        )
        self.bundle = self.run_dir / "verify" / "evidence.json"
        self.evidence = outcome.evidence

    def _rewrite(self, name: str, mutate) -> Path:
        document = json.loads(self.bundle.read_text(encoding="utf-8"))
        mutate(document)
        path = self.run_dir / name
        path.write_text(json.dumps(document, indent=2), encoding="utf-8")
        return path

    def test_a_bundle_straight_from_a_run_verifies(self) -> None:
        code, out, _ = _verify(self.bundle)
        self.assertEqual(code, 0)
        self.assertIn("VERIFIED", out)
        self.assertIn(self.evidence.digest, out)

    def test_an_edited_bundle_is_reported_and_fails(self) -> None:
        path = self._rewrite("edited.json", lambda d: d.__setitem__("result", "FAIL"))
        code, _, err = _verify(path)
        self.assertEqual(code, 1)
        self.assertIn("MODIFIED", err)

    def test_the_edit_that_matters_most_is_caught(self) -> None:
        """
        Rewriting the verdict is the edit someone would actually make.

        Written against the recorded value rather than a literal: the reference
        run passes, so an earlier version of this test set `result` to "PASS"
        on a bundle that already said PASS, changed nothing, and asserted that
        an unchanged document fails to verify. It caught the mistake by
        failing, which is the only reason the assertion was ever worth writing.
        """
        self.assertEqual(self.evidence.result, "PASS")
        path = self._rewrite(
            "demoted.json", lambda d: d.__setitem__("result", "INCOMPLETE")
        )
        self.assertEqual(_verify(path)[0], 1)

    def test_an_edit_deep_inside_the_bundle_is_caught(self) -> None:
        """The digest covers the whole document, not just its headline fields."""

        def bury(document: dict) -> None:
            document["assertions"][0]["passed"] = not document["assertions"][0]["passed"]

        self.assertEqual(_verify(self._rewrite("buried.json", bury))[0], 1)

    def test_a_reformatted_bundle_still_verifies(self) -> None:
        """
        The digest is over a canonical form, so indentation and key order are
        not part of it. A bundle that survived a pretty-printer is not evidence
        of tampering, and reporting it as such would train readers to ignore
        the command.
        """
        document = json.loads(self.bundle.read_text(encoding="utf-8"))
        path = self.run_dir / "reformatted.json"
        path.write_text(
            json.dumps(document, indent=8, sort_keys=True), encoding="utf-8"
        )
        self.assertEqual(_verify(path)[0], 0)

    def test_a_bundle_from_a_newer_beacon_is_not_called_modified(self) -> None:
        """
        An unknown field means this version cannot interpret the bundle. It
        does not mean the bundle was edited, and saying so would be an
        accusation the evidence does not support.
        """

        def from_the_future(document: dict) -> None:
            document["signature"] = {"alg": "not-invented-yet"}
            published = dict(document)
            published["digest"] = ""
            document["digest"] = canonical_digest(published)

        code, out, _ = _verify(self._rewrite("newer.json", from_the_future))
        self.assertEqual(code, 0)
        self.assertIn("VERIFIED", out)
        self.assertIn("cannot read", out)

    def test_the_output_says_what_a_matching_digest_does_not_prove(self) -> None:
        """
        The word VERIFIED invites a stronger reading than the check supports.
        Whatever else the output says, it has to close that gap.
        """
        _, out, _ = _verify(self.bundle)
        self.assertIn("unsigned", out)

    def test_a_bundle_with_no_digest_is_an_error_not_a_pass(self) -> None:
        path = self._rewrite("naked.json", lambda d: d.pop("digest"))
        code, _, err = _verify(path)
        self.assertEqual(code, 2)
        self.assertIn("nothing to verify", err)

    def test_a_file_that_is_not_json_is_an_error(self) -> None:
        path = self.run_dir / "notjson.txt"
        path.write_text("this is not a bundle", encoding="utf-8")
        self.assertEqual(_verify(path)[0], 2)

    def test_json_that_is_not_an_object_is_an_error(self) -> None:
        path = self.run_dir / "list.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")
        code, _, err = _verify(path)
        self.assertEqual(code, 2)
        self.assertIn("not an evidence bundle", err)

    def test_a_missing_file_is_an_error_not_a_crash(self) -> None:
        self.assertEqual(_verify(self.run_dir / "absent.json")[0], 2)


@unittest.skipUnless(SITE.is_dir(), "the site is not present in this checkout")
class PublishedBundleTests(unittest.TestCase):
    """
    Every bundle the site ships must verify against the command the site tells
    readers to use.

    They did not. `build_fixtures.py` replaces the recording machine's path
    with a placeholder *after* the run has sealed itself, so each fixture whose
    command names a path carried a digest over a document that no longer
    existed — published beside a paragraph promising the digest makes an edit
    detectable. Nothing caught it because nothing could check a digest until
    `beacon verify` existed. Rebuilding now reseals the scrubbed document and
    records the substitution in its own `limitations`.
    """

    GENERATED = SITE / "src" / "data" / "generated"

    def test_there_are_published_bundles_to_check(self) -> None:
        self.assertTrue(sorted(self.GENERATED.glob("*/evidence.json")))

    def test_every_published_bundle_verifies(self) -> None:
        for path in sorted(self.GENERATED.glob("*/evidence.json")):
            with self.subTest(bundle=path.parent.name):
                self.assertEqual(_verify(path)[0], 0)

    def test_a_bundle_that_was_edited_says_so(self) -> None:
        """
        Resealing makes the digest match. On its own that would hide the edit
        behind a number that now agrees with it, so the edit is disclosed in
        the document rather than only in the tool that made it.
        """
        edited = [
            path
            for path in sorted(self.GENERATED.glob("*/evidence.json"))
            if "<repo>" in path.read_text(encoding="utf-8")
        ]
        self.assertTrue(edited, "no fixture carries the placeholder any more")
        for path in edited:
            with self.subTest(bundle=path.parent.name):
                limitations = json.loads(path.read_text(encoding="utf-8"))["limitations"]
                self.assertTrue(
                    any("replaced with" in item for item in limitations),
                    "the bundle was edited and does not admit it",
                )


if __name__ == "__main__":
    unittest.main()
