from __future__ import annotations

import unittest
from unittest import mock

from beacon.cli import split_command


class PosixSplitTests(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch("beacon.cli.os.name", "posix")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_plain_command(self) -> None:
        self.assertEqual(
            split_command("python examples/subjects/well_behaved.py"),
            ["python", "examples/subjects/well_behaved.py"],
        )

    def test_quoted_paths_with_spaces(self) -> None:
        self.assertEqual(
            split_command("python 'my agent/run.py' --flag"),
            ["python", "my agent/run.py", "--flag"],
        )


class WindowsSplitTests(unittest.TestCase):
    """
    Windows paths through a POSIX splitter lose their separators entirely:
    `examples\\subjects\\agent.py` becomes `examplessubjectsagent.py`, and the
    run fails with a file-not-found that names a path nobody typed.
    """

    def setUp(self) -> None:
        patcher = mock.patch("beacon.cli.os.name", "nt")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_backslash_paths_survive(self) -> None:
        self.assertEqual(
            split_command(r"python examples\subjects\well_behaved.py"),
            ["python", r"examples\subjects\well_behaved.py"],
        )

    def test_forward_slashes_also_work(self) -> None:
        self.assertEqual(
            split_command("python examples/subjects/well_behaved.py"),
            ["python", "examples/subjects/well_behaved.py"],
        )

    def test_a_quoted_path_with_spaces_loses_its_quotes(self) -> None:
        self.assertEqual(
            split_command(r'python "C:\Program Files\agent\run.py"'),
            ["python", r"C:\Program Files\agent\run.py"],
        )

    def test_a_drive_absolute_path_survives(self) -> None:
        self.assertEqual(
            split_command(r"C:\Python313\python.exe agent.py"),
            [r"C:\Python313\python.exe", "agent.py"],
        )

    def test_flags_are_untouched(self) -> None:
        self.assertEqual(
            split_command(r"python agent.py --model claude-sonnet-5"),
            ["python", "agent.py", "--model", "claude-sonnet-5"],
        )


if __name__ == "__main__":
    unittest.main()
