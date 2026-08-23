from __future__ import annotations

"""
One module per group of subcommands, each returning a process exit code.

Every handler takes the parsed `argparse.Namespace` (or the one value it needs)
and returns an int. None of them raise for an operator error: `cli.main` owns
the single `except` that turns a `ScenarioError` into `error: ...` and exit 2,
so the rule that a run always produces evidence has one place to live.
"""

from beacon.commands.authoring import init, prove, validate
from beacon.commands.catalog import adapters, scenarios, taxonomy
from beacon.commands.probe import a2a_inspect, mcp_inspect
from beacon.commands.run import report_baseline, run, serve_mcp
from beacon.commands.verify import verify

__all__ = [
    "a2a_inspect",
    "adapters",
    "init",
    "mcp_inspect",
    "prove",
    "report_baseline",
    "run",
    "scenarios",
    "serve_mcp",
    "taxonomy",
    "validate",
    "verify",
]
