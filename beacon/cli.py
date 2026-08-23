from __future__ import annotations

"""
Dispatch, and the one place an operator error becomes an exit code.

This module was 1,095 lines: the adapter table, a 372-line `build_parser`, and
twelve handlers, all in one file. It is now the seam between them — `cliargs`
builds the parser, `beacon/commands/` does the work, and `main` maps a
subcommand to a handler and owns the single `except` that turns a
`ScenarioError` into `error: ...` and exit 2.

The names below are re-exported rather than moved out of reach. `beacon.cli` is
what the tests, `site/tools/build_fixtures.py` and anyone else import from, and
a refactor that quietly changed that import path would be a breaking change
dressed up as tidying.
"""

import sys
from typing import Sequence

from beacon.cliadapters import ADAPTERS, RUN_ADAPTERS, AdapterSpec, adapter_rows
from beacon.cliargs import build_parser, split_command
from beacon.commands import (
    a2a_inspect,
    adapters,
    init,
    mcp_inspect,
    prove,
    report_baseline,
    run,
    scenarios,
    serve_mcp,
    taxonomy,
    validate,
    verify,
)
from beacon.models import ScenarioError
from beacon.protocols import A2AError, MCPError
from beacon.secrets import SecretError

#: `tests/test_cli_adapters.py` imports this name. It was private when the
#: listing lived here; the alias keeps the import working rather than making a
#: test edit part of the cost of moving a function.
_adapters = adapters

__all__ = [
    "ADAPTERS",
    "RUN_ADAPTERS",
    "AdapterSpec",
    "adapter_rows",
    "build_parser",
    "main",
    "split_command",
]

#: Subcommand name to handler. A dict rather than an if-chain because the two
#: things that must agree — the parser's subcommands and the handlers — are now
#: in different modules, and `tests/test_cli_adapters.py` can compare the two
#: sets directly instead of trusting that a reader noticed a missing branch.
COMMANDS = {
    "validate": lambda args: validate(args.scenario, args.service_module),
    "prove": prove,
    "verify": lambda args: verify(args.evidence),
    "init": init,
    "run": run,
    "serve-mcp": serve_mcp,
    "scenarios": lambda args: scenarios(),
    "taxonomy": taxonomy,
    "adapters": lambda args: adapters(),
    "mcp-inspect": mcp_inspect,
    "a2a-inspect": a2a_inspect,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = COMMANDS.get(args.command_name)
    if handler is None:
        parser.error(f"unknown command: {args.command_name}")
        return 2
    try:
        return handler(args)
    except (
        ScenarioError,
        SecretError,
        MCPError,
        A2AError,
        OSError,
        ValueError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
