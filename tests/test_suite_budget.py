from __future__ import annotations

import json
import unittest
from pathlib import Path

import sys as _sys
from pathlib import Path as _Path

# `unittest discover -s tests` puts this directory on the path; running a
# module directly as `python3 -m unittest tests.test_x` does not. Both forms
# get used, so make the sibling import work either way.
_sys.path.insert(0, str(_Path(__file__).resolve().parent))

from _subject_runs import runs_performed


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples" / "subjects" / "manifest.json"


class SubjectRunBudgetTests(unittest.TestCase):
    """
    One subprocess per subject, however many harnesses want the answer.

    Four harnesses drive the adversarial subjects, and each used to spawn its
    own copy: `test_adversarial_subjects` twice from two tests making the
    identical call, `test_falsifiability` once more, and the site's fixture
    builder again. The subjects are deterministic and the runner is tested to
    be, so the extra runs bought nothing.

    The reason this is a test rather than a note is that the regression is
    invisible. A fifth harness that spawns everything again does not fail
    anything; it makes CI slower, gradually, and by the time anyone measures it
    the change responsible is months back. At the ~330 manifest entries a
    55-scenario suite implies, one careless duplication is minutes per leg
    across nine legs.

    Counts, deliberately, not seconds. A wall-clock assertion on a shared CI
    runner is a flake generator, and the thing worth protecting is the
    invariant rather than any particular speed.
    """

    def test_no_subject_is_run_more_than_once(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        entries = len(manifest["subjects"])
        performed = runs_performed()

        # Zero means this module ran alone: nothing has asked for a subject run
        # in this process, so there is no duplication to detect and nothing to
        # assert about.
        if performed == 0:
            self.skipTest("no subject runs in this process; nothing to budget")

        self.assertLessEqual(
            performed,
            entries,
            f"{performed} subject runs for {entries} manifest entries. Some "
            f"harness is spawning subjects instead of asking "
            f"tests/_subject_runs.py for them.",
        )
