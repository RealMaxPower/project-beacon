from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Sequence

from beacon import __version__
from beacon.adapters import JSONLCommandAdapter, ReferenceInboxAdapter
from beacon.determinism import compare_runs, repeat_run_ids
from beacon.models import Scenario, ScenarioError
from beacon.protocols import A2AClient, A2AError, MCPError, MCPStdioClient
from beacon.runner import run_scenario


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
        prog="beacon",
        description=(
            "Protocol-neutral trial and readiness evidence for agents and tools."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    validate = subparsers.add_parser("validate", help="Validate a scenario file.")
    validate.add_argument("scenario", type=Path)

    run = subparsers.add_parser("run", help="Run a scenario and write evidence.")
    run.add_argument("scenario", type=Path)
    run.add_argument(
        "--adapter",
        choices=("reference", "command"),
        default="reference",
    )
    run.add_argument(
        "--command",
        help="JSONL subject command, parsed with shell-like quoting.",
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
        "--repeat",
        type=int,
        default=1,
        metavar="N",
        help=(
            "Run the scenario N times and report whether the verdict, state "
            "digests, and assertion results are identical across runs."
        ),
    )

    adapters = subparsers.add_parser(
        "adapters",
        help="List built-in subject and protocol adapters.",
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
    return parser


def _validate(path: Path) -> int:
    scenario = Scenario.load(path)
    print(
        json.dumps(
            {
                "valid": True,
                "id": scenario.id,
                "name": scenario.name,
                "assertions": len(scenario.assertions),
                "services": sorted(scenario.fixtures),
            },
            indent=2,
        )
    )
    return 0


def _run(args: argparse.Namespace) -> int:
    scenario = Scenario.load(args.scenario)
    if args.repeat < 1:
        raise ScenarioError("--repeat must be at least 1")
    if args.adapter == "reference":
        if args.command:
            raise ScenarioError("--command can only be used with --adapter command")
        adapter = ReferenceInboxAdapter()
    else:
        if not args.command:
            raise ScenarioError("--adapter command requires --command")
        adapter = JSONLCommandAdapter(
            shlex.split(args.command),
            timeout_seconds=args.timeout,
        )

    outcomes = [
        run_scenario(scenario, adapter, output_dir=args.output, run_id=run_id)
        for run_id in repeat_run_ids(args.run_id, args.repeat)
    ]

    if args.repeat == 1:
        outcome = outcomes[0]
        print(f"{outcome.evidence.result}: {scenario.name}")
        print(f"Evidence: {outcome.json_path}")
        print(f"Report:   {outcome.markdown_path}")
        return 0 if outcome.evidence.result == "PASS" else 1

    for index, outcome in enumerate(outcomes, start=1):
        print(
            f"[{index}/{args.repeat}] {outcome.evidence.result}: "
            f"{outcome.evidence.run_id}"
        )
    report = compare_runs([outcome.evidence for outcome in outcomes])
    print(report.summary())
    passed = all(outcome.evidence.result == "PASS" for outcome in outcomes)
    return 0 if passed and report.stable else 1


def _adapters() -> int:
    rows = [
        {
            "id": "reference",
            "subject": "Beacon reference inbox agent",
            "interface": "in-process",
            "level": 4,
            "status": "MVP",
        },
        {
            "id": "command",
            "subject": "Any wrapped CLI/API/SDK agent",
            "interface": "bidirectional JSONL",
            "level": 3,
            "status": "MVP",
        },
        {
            "id": "mcp-stdio",
            "subject": "MCP server",
            "interface": "MCP stdio",
            "level": 1,
            "status": "inspect/call",
        },
        {
            "id": "a2a-http",
            "subject": "A2A agent",
            "interface": "A2A v1.0 HTTP+JSON or JSON-RPC",
            "level": 2,
            "status": "discover/send spike",
        },
    ]
    print(json.dumps(rows, indent=2))
    return 0


def _mcp_inspect(args: argparse.Namespace) -> int:
    command = shlex.split(args.command)
    with MCPStdioClient(command, timeout_seconds=args.timeout) as client:
        tools = client.list_tools()
        output = {
            "protocol_version": client.protocol_version,
            "server_info": client.server_info,
            "capabilities": client.capabilities,
            "tools": tools,
        }
        if args.call:
            output["call"] = {
                "tool": args.call,
                "arguments": args.arguments,
                "result": client.call_tool(args.call, args.arguments),
            }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


def _a2a_inspect(args: argparse.Namespace) -> int:
    client = A2AClient(
        args.url,
        timeout_seconds=args.timeout,
        authorization=args.authorization,
    )
    output = {"agent_card": client.discover()}
    if args.send:
        output["response"] = client.send_message(args.send)
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command_name == "validate":
            return _validate(args.scenario)
        if args.command_name == "run":
            return _run(args)
        if args.command_name == "adapters":
            return _adapters()
        if args.command_name == "mcp-inspect":
            return _mcp_inspect(args)
        if args.command_name == "a2a-inspect":
            return _a2a_inspect(args)
        parser.error(f"unknown command: {args.command_name}")
    except (ScenarioError, MCPError, A2AError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

