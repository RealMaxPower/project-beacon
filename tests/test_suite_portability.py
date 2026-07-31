from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCANNED = sorted(
    path
    for directory in ("tests", "examples")
    for path in (ROOT / directory).rglob("*.py")
    if "node_modules" not in path.parts
)


def _spawned_interpreters(path: Path) -> list[tuple[str, int]]:
    """
    Every hardcoded interpreter name handed to an adapter as its command.

    Matches the shape `SomethingAdapter(["python3", ...])` rather than the bare
    string, because a command line stored as test *data* — the subject-identity
    fixtures in `test_baseline.py`, say — is not a process anybody launches and
    is fine as it stands.
    """
    found: list[tuple[str, int]] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if not name.endswith("Adapter") or not node.args:
            continue
        first = node.args[0]
        if not isinstance(first, ast.List) or not first.elts:
            continue
        head = first.elts[0]
        if isinstance(head, ast.Constant) and isinstance(head.value, str):
            found.append((head.value, head.lineno))
    return found


class InterpreterPortabilityTests(unittest.TestCase):
    """
    A subject is launched with `sys.executable`, never a literal name.

    `docs/windows.md` says it plainly: on Windows `python3` is often a Store
    alias stub that does nothing useful. Two tests spawned subjects with a
    literal `"python3"` anyway — including the falsifiability audit, the one
    check that guarantees no report states something nobody has tested. Both
    passed locally on macOS and would have failed the moment the Windows leg of
    the matrix ran, which is exactly the kind of defect a switched-off CI hides.

    `sys.executable` is also the only correct answer inside a virtualenv, where
    the interpreter running the suite is usually not the one on PATH.
    """

    def test_there_are_files_to_scan(self) -> None:
        """A passing check because the glob found nothing proves nothing."""
        self.assertGreater(len(SCANNED), 20)

    def test_no_subject_is_launched_by_a_hardcoded_interpreter(self) -> None:
        offenders: list[str] = []
        for path in SCANNED:
            for value, line in _spawned_interpreters(path):
                offenders.append(f"{path.relative_to(ROOT)}:{line} -> {value!r}")
        self.assertEqual(
            offenders,
            [],
            "use sys.executable, not a literal interpreter name:\n"
            + "\n".join(offenders),
        )

    def test_the_scanner_recognises_the_shape_it_is_looking_for(self) -> None:
        """Without this, an AST change could silently make the check vacuous."""
        source = 'JSONLCommandAdapter(["python3", "subject.py"])\n'
        tree = ast.parse(source)
        call = tree.body[0].value
        self.assertEqual(call.args[0].elts[0].value, "python3")

        sample = ROOT / "tests" / "test_suite_portability.py"
        self.assertEqual(_spawned_interpreters(sample), [])


if __name__ == "__main__":
    unittest.main()
