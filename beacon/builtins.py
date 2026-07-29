from __future__ import annotations

from pathlib import Path


"""
Find the scenarios Beacon ships, whether it was cloned or installed.

`pip install project-beacon` gives you a working CLI, and until this existed
it gave you nothing to point it at: every command in the README names a path
under `scenarios/`, which only exists in a checkout. The first thing a new
user tried therefore failed.

The files themselves stay at the repository root, where they are easy to read
and edit. The build maps that directory into the package as
`beacon/builtin_scenarios`, so the two layouts differ and both are supported
here rather than anywhere else.
"""


def _candidate_roots() -> tuple[Path, ...]:
    package = Path(__file__).resolve().parent
    return (
        # Installed from a wheel: the build copied scenarios/ in here.
        package / "builtin_scenarios",
        # A checkout, or an editable install pointing back at one.
        package.parent / "scenarios",
    )


def builtin_root() -> Path | None:
    for root in _candidate_roots():
        if root.is_dir() and any(root.glob("*/scenario.json")):
            return root
    return None


def builtin_names() -> tuple[str, ...]:
    root = builtin_root()
    if root is None:
        return ()
    return tuple(sorted(path.parent.name for path in root.glob("*/scenario.json")))


def resolve_scenario(value: str | Path) -> Path:
    """
    Turn a CLI argument into a scenario file.

    A path always wins over a built-in name. Someone who has cloned the repo
    and edited `scenarios/inbox-briefing/scenario.json` must get their copy,
    not a pristine one from site-packages, or they would edit a file and see
    no change.
    """
    path = Path(value)
    if path.exists():
        return path

    # Not a path that exists. If it looks like one, say so plainly rather than
    # reporting it as an unknown built-in name.
    if path.suffix or len(path.parts) > 1:
        raise FileNotFoundError(f"scenario does not exist: {value}")

    root = builtin_root()
    if root is not None:
        candidate = root / str(value) / "scenario.json"
        if candidate.is_file():
            return candidate

    available = ", ".join(builtin_names()) or "none found"
    # str(), not repr(): argparse has already turned this into a Path, and
    # "PosixPath('nope')" in an error message is noise the reader has to
    # translate back.
    raise FileNotFoundError(
        f"no scenario file at {str(value)!r}, and no built-in scenario by "
        f"that name. Built-in scenarios: {available}"
    )
