from __future__ import annotations

"""
Argument parsing: the command surface, and nothing that acts on it.

`build_parser` was three hundred and seventy lines inside a module that also
held every handler. Keeping the two apart means a new subcommand touches the
parser here and its behaviour in `beacon/commands/`, rather than growing one
file further in both directions at once.
"""

import argparse
import json
import os
import shlex
from pathlib import Path

from beacon import __version__
from beacon.cliadapters import RUN_ADAPTERS


def split_command(text: str) -> list[str]:
    """
    Split a `--command` string into argv, correctly on every platform.

    `shlex.split` assumes POSIX quoting, where a backslash escapes the next
    character — so on Windows `python examples\\subjects\\agent.py` silently
    becomes `examplessubjectsagent.py` and the run fails with a confusing
    "file not found". Windows uses non-POSIX rules, which keep the separators
    but leave quotes attached to the tokens, so those are stripped back off.
    """
    if os.name != "nt":
        return shlex.split(text)
    tokens = shlex.split(text, posix=False)
    return [
        token[1:-1]
        if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'"
        else token
        for token in tokens
    ]


def _json_object(value: str) -> dict:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise argparse.ArgumentTypeError(f"invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("value must be a JSON object")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        # Matches the installed command, so `--help` does not advertise a
        # binary name that no longer exists.
        prog="project-beacon",
        description=(
            "Protocol-neutral trial and readiness evidence for agents and tools."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    validate = subparsers.add_parser("validate", help="Validate a scenario file.")
    validate.add_argument("scenario", type=Path, help="Path to a scenario file, or the name of a built-in scenario (see `project-beacon scenarios`).")
    validate.add_argument(
        "--service-module",
        action="append",
        default=[],
        metavar="MODULE",
        help=(
            "Import this module first, so a service it registers is "
            "recognised rather than reported as a plain data fixture."
        ),
    )

    prove = subparsers.add_parser(
        "prove",
        help="Check that every assertion in a scenario has a subject that makes it fail.",
        description=(
            "An assertion nobody has watched fail is a claim the evidence does "
            "not support, and report.md prints its description as a finding "
            "either way. This runs your subjects against the scenario and names "
            "every assertion none of them broke."
        ),
    )
    prove.add_argument(
        "scenario",
        type=Path,
        help="Path to a scenario file, or the name of a built-in scenario.",
    )
    prove.add_argument(
        "--subject",
        action="append",
        default=[],
        metavar="PATH",
        type=Path,
        help=(
            "A subject to run. Repeatable. Omit to use every `subjects/*.py` "
            "beside the scenario, which is what `init` scaffolds."
        ),
    )
    prove.add_argument(
        "--timeout",
        type=float,
        default=None,
        metavar="SECONDS",
        help="Per-subject timeout. Omit to use the scenario's own limit.",
    )
    prove.add_argument(
        "--service-module",
        action="append",
        default=[],
        metavar="MODULE",
        help="Import this module first, so a service it registers is recognised.",
    )
    prove.add_argument(
        "--json", action="store_true", help="Emit the report as JSON."
    )

    verify = subparsers.add_parser(
        "verify",
        help="Recompute an evidence bundle's digest and report whether it matches.",
    )
    verify.add_argument(
        "evidence",
        type=Path,
        help="Path to an evidence.json written by a run.",
    )

    run = subparsers.add_parser("run", help="Run a scenario and write evidence.")
    run.add_argument("scenario", type=Path, help="Path to a scenario file, or the name of a built-in scenario (see `project-beacon scenarios`).")
    run.add_argument(
        "--adapter",
        choices=tuple(spec.flag for spec in RUN_ADAPTERS),
        default="reference",
    )
    run.add_argument(
        "--command",
        help="JSONL subject command, parsed with shell-like quoting.",
    )
    run.add_argument(
        "--agent-url",
        help="Base URL of a hosted A2A agent, for --adapter a2a.",
    )
    run.add_argument(
        "--mcp-url",
        help=(
            "Streamable HTTP endpoint of the MCP server under test, for "
            "--adapter mcp-tool. This is the complete endpoint, not a base "
            "URL: unlike --agent-url there is nothing to discover."
        ),
    )
    run.add_argument(
        "--tool",
        help="Tool to call as the subject, for --adapter mcp-tool.",
    )
    run.add_argument(
        "--arguments",
        type=_json_object,
        default={},
        metavar="JSON",
        help="JSON object of arguments for --tool.",
    )
    run.add_argument(
        "--artifact-name",
        help=(
            "Record the tool's answer under this name instead of the "
            "adapter's default, for --adapter mcp-tool. It has to match the "
            "artifact the scenario's output contract requires."
        ),
    )
    run.add_argument(
        "--authorization",
        # A credential on the command line lands in shell history, which is
        # why every other secret here arrives by environment name. This flag
        # predates that rule rather than being exempt from it.
        help=(
            "Complete Authorization header value for --adapter a2a and "
            "--adapter mcp-tool."
        ),
    )
    run.add_argument(
        "--allow-agent-origin",
        action="append",
        default=[],
        metavar="ORIGIN",
        help=(
            "Also let the Agent Card send Beacon to this origin, such as "
            "https://host:8443. By default only --agent-url's own origin is "
            "requested, because the card is written by the agent under "
            "evaluation. An allowed extra origin never receives "
            "--authorization. Repeatable."
        ),
    )
    run.add_argument(
        "--output",
        type=Path,
        default=Path(".beacon/runs"),
        help="Directory that receives immutable run folders.",
    )
    run.add_argument(
        "--timeout",
        type=float,
        help=(
            "Override the scenario's declared timeout. The override is "
            "recorded in the evidence bundle."
        ),
    )
    run.add_argument(
        "--run-id",
        help="Fixed run identifier. Repeats are suffixed -001, -002, and so on.",
    )
    run.add_argument(
        "--env-passthrough",
        action="append",
        default=[],
        metavar="NAME",
        help=(
            "Copy this environment variable to the subject. Names only; the "
            "value is read from Beacon's own environment. Repeatable."
        ),
    )
    run.add_argument(
        "--env-secret",
        action="append",
        default=[],
        metavar="NAME",
        help=(
            "Like --env-passthrough, but the value is also removed from the "
            "evidence bundle wherever it appears. Use for API keys. Repeatable."
        ),
    )
    run.add_argument(
        "--baseline",
        type=Path,
        metavar="PATH",
        help=(
            "Compare this run against a recorded baseline, and write one if "
            "the file does not exist. Exits non-zero on a regression."
        ),
    )
    run.add_argument(
        "--service-module",
        action="append",
        default=[],
        metavar="MODULE",
        help=(
            "Import this module before running, so a service it registers is "
            "available to the scenario. Accepts a dotted name or a path to a "
            ".py file. Repeatable."
        ),
    )
    run.add_argument(
        "--baseline-recent",
        type=int,
        metavar="N",
        help=(
            "Compare this run against the last N runs of the same scenario "
            "and subject already in --output. Needs no committed file, and "
            "reports nothing on the first run. Exits non-zero on a regression."
        ),
    )
    run.add_argument(
        "--baseline-tolerance",
        type=float,
        default=0.0,
        metavar="RATE",
        help=(
            "Allow a pass rate to drop this much before calling it a "
            "regression, as a fraction: 0.1 permits ten points of sampling "
            "noise. Defaults to 0, which reports any drop."
        ),
    )
    run.add_argument(
        "--repeat",
        type=int,
        default=1,
        metavar="N",
        help=(
            "Run the scenario N times and report whether the verdict, state "
            "digests, and assertion results are identical across runs."
        ),
    )

    init = subparsers.add_parser(
        "init",
        help="Generate a runnable scenario, with the subjects that prove it grades.",
    )
    init.add_argument(
        "scenario_id",
        help="Lowercase, hyphenated, e.g. refund-policy-grounding.",
    )
    init.add_argument(
        "--dir",
        type=Path,
        default=Path("scenarios"),
        help="Where the scenario directory is created. Default: scenarios/",
    )
    init.add_argument(
        "--service",
        metavar="NAME",
        help=(
            "Also generate a synthetic service under this fixture name, and a "
            "scenario graded on its state rather than on the answer text. "
            "Omit for a black-box scenario against a hosted agent."
        ),
    )
    init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files.",
    )

    subparsers.add_parser(
        "scenarios",
        help="List the scenarios shipped with this installation.",
    )

    taxonomy = subparsers.add_parser(
        "taxonomy",
        help="Show the failure taxonomy and how much of it the scenarios cover.",
    )
    taxonomy.add_argument(
        "--json",
        action="store_true",
        help="Emit the coverage report as JSON.",
    )
    taxonomy.add_argument(
        "--uncovered",
        action="store_true",
        help="List the gradeable cells no scenario covers yet.",
    )

    adapters = subparsers.add_parser(
        "adapters",
        help="List built-in subject and protocol adapters.",
    )

    serve = subparsers.add_parser(
        "serve-mcp",
        help="Serve a scenario's tools over MCP and wait for a host to connect.",
    )
    serve.add_argument("scenario", type=Path, help="Path to a scenario file, or the name of a built-in scenario (see `project-beacon scenarios`).")
    serve.add_argument(
        "--output",
        type=Path,
        default=Path(".beacon/runs"),
        help="Directory that receives immutable run folders.",
    )
    serve.add_argument("--run-id")
    serve.add_argument(
        "--timeout",
        type=float,
        help="How long to wait for a submission. Defaults to the scenario's limit.",
    )
    serve.add_argument(
        "--port",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Bind the façade to this loopback port instead of an ephemeral "
            "one, so a GUI host's stored connector stays valid between runs."
        ),
    )
    serve.add_argument(
        "--token-env",
        metavar="NAME",
        help=(
            "Read the bearer token from this environment variable instead of "
            "generating a fresh one per run. Names only — a token on the "
            "command line ends up in your shell history."
        ),
    )
    # Without this, a scenario pack that brings its own service could be run
    # and validated but never served to a GUI host: the two headline features
    # did not compose, and the failure read as "scenario scopes tools but
    # defines no supported service fixture".
    serve.add_argument(
        "--service-module",
        action="append",
        default=[],
        metavar="MODULE",
        help=(
            "Import this module first, so a service it registers is "
            "recognised rather than reported as a plain data fixture."
        ),
    )

    mcp = subparsers.add_parser(
        "mcp-inspect",
        help="Initialize an MCP stdio server and list its tools.",
    )
    mcp.add_argument("--command", required=True)
    mcp.add_argument("--call", help="Optional MCP tool name to call.")
    mcp.add_argument("--arguments", type=_json_object, default={})
    mcp.add_argument("--timeout", type=float, default=10)

    a2a = subparsers.add_parser(
        "a2a-inspect",
        help="Discover an A2A Agent Card and optionally send a message.",
    )
    a2a.add_argument("url")
    a2a.add_argument("--send", help="Optional message to send to the agent.")
    a2a.add_argument("--timeout", type=float, default=10)
    a2a.add_argument(
        "--authorization",
        help="Complete Authorization header value, such as 'Bearer ...'.",
    )
    a2a.add_argument(
        "--allow-agent-origin",
        action="append",
        default=[],
        metavar="ORIGIN",
        help=(
            "Also let the Agent Card send Beacon to this origin, such as "
            "https://host:8443. By default only the given URL's own origin is "
            "requested. An allowed extra origin never receives "
            "--authorization. Repeatable."
        ),
    )
    return parser
