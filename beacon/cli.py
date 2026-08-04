from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from pathlib import Path
from typing import Sequence

from beacon import __version__
from beacon.adapters import (
    A2ASubjectAdapter,
    JSONLCommandAdapter,
    MCPHostAdapter,
    MCPServeAdapter,
    ReferenceInboxAdapter,
)
from beacon.builtins import builtin_names, builtin_root, resolve_scenario
from beacon.baseline import (
    build_baseline,
    compare_to_baseline,
    load_baseline,
    load_recent_evidence,
    save_baseline,
)
from beacon.determinism import compare_runs, repeat_run_ids
from beacon.models import Evidence, Scenario, ScenarioError
from beacon.protocols import A2AClient, A2AError, MCPError, MCPStdioClient
from beacon.scaffold import scaffold
from beacon.secrets import SecretError, looks_like_a_secret
from beacon.runner import run_scenario
from beacon.services import import_service_module, is_service


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
        prog="beacon",
        description=(
            "Protocol-neutral trial and readiness evidence for agents and tools."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command_name", required=True)

    validate = subparsers.add_parser("validate", help="Validate a scenario file.")
    validate.add_argument("scenario", type=Path, help="Path to a scenario file, or the name of a built-in scenario (see `beacon scenarios`).")
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

    run = subparsers.add_parser("run", help="Run a scenario and write evidence.")
    run.add_argument("scenario", type=Path, help="Path to a scenario file, or the name of a built-in scenario (see `beacon scenarios`).")
    run.add_argument(
        "--adapter",
        choices=("reference", "command", "mcp-host", "a2a"),
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
        "--authorization",
        help="Complete Authorization header value for --adapter a2a.",
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

    adapters = subparsers.add_parser(
        "adapters",
        help="List built-in subject and protocol adapters.",
    )

    serve = subparsers.add_parser(
        "serve-mcp",
        help="Serve a scenario's tools over MCP and wait for a host to connect.",
    )
    serve.add_argument("scenario", type=Path, help="Path to a scenario file, or the name of a built-in scenario (see `beacon scenarios`).")
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


def _validate(path: Path, service_modules: Sequence[str] = ()) -> int:
    for module in service_modules:
        import_service_module(module)
    scenario = Scenario.load(resolve_scenario(path))
    print(
        json.dumps(
            {
                "valid": True,
                "id": scenario.id,
                "name": scenario.name,
                "assertions": len(scenario.assertions),
                # A fixture is only a service if something is registered under
                # that name. Calling a plain data fixture a service implies the
                # subject gets tools it will never be offered.
                "services": sorted(
                    name for name in scenario.fixtures if is_service(name)
                ),
                "data_fixtures": sorted(
                    name for name in scenario.fixtures if not is_service(name)
                ),
            },
            indent=2,
        )
    )
    return 0


def _report_baseline(
    args: argparse.Namespace, evidences: Sequence[Evidence]
) -> bool:
    """Print the baseline comparison, if one was asked for. True on regression."""
    if args.baseline:
        if args.baseline.exists():
            comparison = compare_to_baseline(
                evidences,
                load_baseline(args.baseline),
                tolerance=args.baseline_tolerance,
                source=str(args.baseline),
            )
            print(comparison.summary())
            return comparison.regressed
        save_baseline(evidences, args.baseline)
        print(
            f"Baseline: recorded {len(evidences)} run(s) to {args.baseline}. "
            f"Future runs will be compared against it."
        )
        return False

    if args.baseline_recent:
        history = load_recent_evidence(
            args.output,
            like=evidences[0],
            exclude_run_ids=[evidence.run_id for evidence in evidences],
            limit=args.baseline_recent,
        )
        if not history:
            # The first run of a scenario has nothing to be worse than. Saying
            # so is better than printing an empty comparison that reads like a
            # clean bill of health.
            print(
                "Baseline: no earlier runs of this scenario and subject in "
                f"{args.output}. Recording this run as the first."
            )
            return False
        comparison = compare_to_baseline(
            evidences,
            build_baseline(history),
            tolerance=args.baseline_tolerance,
            source=f"last {len(history)} run(s)",
        )
        print(comparison.summary())
        return comparison.regressed

    return False


def _init(args: argparse.Namespace) -> int:
    created = scaffold(
        args.scenario_id, args.dir, service=args.service, force=args.force
    )
    for path in created:
        print(f"created  {path}")
    directory = args.dir / args.scenario_id
    print()
    print(f"Next: {directory / 'README.md'} has the two commands to run.")
    print("The second one is meant to fail. That is how you know it grades.")
    return 0


def _run(args: argparse.Namespace) -> int:
    for module in args.service_module:
        import_service_module(module)
    scenario = Scenario.load(resolve_scenario(args.scenario))
    if args.repeat < 1:
        raise ScenarioError("--repeat must be at least 1")
    if args.baseline and args.baseline_recent:
        raise ScenarioError(
            "--baseline and --baseline-recent are two different questions. "
            "A file baseline asks whether this is worse than the version you "
            "blessed; --baseline-recent asks whether it is worse than "
            "yesterday. Pick one."
        )
    if args.baseline_recent is not None and args.baseline_recent < 1:
        raise ScenarioError("--baseline-recent must be at least 1")
    if not 0.0 <= args.baseline_tolerance < 1.0:
        raise ScenarioError("--baseline-tolerance must be a fraction in [0, 1)")
    unmarked = [name for name in args.env_passthrough if looks_like_a_secret(name)]
    if unmarked:
        raise ScenarioError(
            f"{', '.join(unmarked)} looks like a credential. Use --env-secret "
            f"so the value is redacted from the evidence bundle, which is the "
            f"artifact people share."
        )
    if args.adapter == "reference":
        if args.command:
            raise ScenarioError("--command can only be used with --adapter command")
        if args.env_passthrough or args.env_secret:
            raise ScenarioError(
                "environment options apply to --adapter command only; the "
                "reference subject runs in process"
            )
        adapter = ReferenceInboxAdapter()
    elif args.adapter == "a2a":
        if not args.agent_url:
            raise ScenarioError("--adapter a2a requires --agent-url")
        adapter = A2ASubjectAdapter(
            args.agent_url,
            timeout_seconds=args.timeout,
            authorization=args.authorization,
            allowed_origins=args.allow_agent_origin,
        )
    elif args.adapter == "mcp-host":
        if not args.command:
            raise ScenarioError("--adapter mcp-host requires --command")
        adapter = MCPHostAdapter(
            split_command(args.command),
            timeout_seconds=args.timeout,
            env_passthrough=args.env_passthrough,
            env_secrets=args.env_secret,
        )
    else:
        if not args.command:
            raise ScenarioError("--adapter command requires --command")
        adapter = JSONLCommandAdapter(
            split_command(args.command),
            timeout_seconds=args.timeout,
            env_passthrough=args.env_passthrough,
            env_secrets=args.env_secret,
        )

    outcomes = [
        run_scenario(scenario, adapter, output_dir=args.output, run_id=run_id)
        for run_id in repeat_run_ids(args.run_id, args.repeat)
    ]

    evidences = [outcome.evidence for outcome in outcomes]

    if args.repeat == 1:
        outcome = outcomes[0]
        print(f"{outcome.evidence.result}: {scenario.name}")
        print(f"Evidence: {outcome.json_path}")
        print(f"Report:   {outcome.markdown_path}")
    else:
        for index, outcome in enumerate(outcomes, start=1):
            print(
                f"[{index}/{args.repeat}] {outcome.evidence.result}: "
                f"{outcome.evidence.run_id}"
            )
        print(compare_runs(evidences).summary())

    regressed = _report_baseline(args, evidences)

    stable = args.repeat == 1 or compare_runs(evidences).stable
    passed = all(evidence.result == "PASS" for evidence in evidences)
    return 0 if passed and stable and not regressed else 1


def _serve_mcp(args: argparse.Namespace) -> int:
    for module in args.service_module:
        import_service_module(module)
    scenario = Scenario.load(resolve_scenario(args.scenario))
    token = None
    if args.token_env:
        token = os.environ.get(args.token_env)
        if not token:
            raise ScenarioError(
                f"{args.token_env} is not set. Export a token first, or drop "
                f"--token-env to have one generated for this run."
            )
    outcome = run_scenario(
        scenario,
        MCPServeAdapter(
            timeout_seconds=args.timeout, port=args.port, token=token
        ),
        output_dir=args.output,
        run_id=args.run_id,
    )
    print()
    print(f"{outcome.evidence.result}: {scenario.name}")
    print(f"Evidence: {outcome.json_path}")
    print(f"Report:   {outcome.markdown_path}")
    return 0 if outcome.evidence.result == "PASS" else 1


def _scenarios() -> int:
    root = builtin_root()
    names = builtin_names()
    if not names:
        print(
            "No built-in scenarios found in this installation.", file=sys.stderr
        )
        return 2
    print(f"Built-in scenarios ({root}):")
    for name in names:
        scenario = Scenario.load(root / name / "scenario.json")
        print(f"  {name:32} {scenario.name}")
    print()
    print("Run one by name, with no path:  beacon run inbox-briefing")
    return 0


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
            "id": "mcp-host",
            "subject": "Any MCP-speaking agent host",
            "interface": "Beacon serves MCP over HTTP; adapter owns lifecycle",
            "level": 1,
            "status": "MVP",
        },
        {
            "id": "mcp-serve",
            "subject": "An MCP host you connect yourself",
            "interface": "Beacon serves MCP over HTTP and waits",
            "level": 1,
            "status": "MVP",
        },
        {
            "id": "mcp-stdio",
            "subject": "MCP server",
            "interface": "MCP stdio client",
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
    command = split_command(args.command)
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
        allowed_origins=args.allow_agent_origin,
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
            return _validate(args.scenario, args.service_module)
        if args.command_name == "init":
            return _init(args)
        if args.command_name == "run":
            return _run(args)
        if args.command_name == "serve-mcp":
            return _serve_mcp(args)
        if args.command_name == "scenarios":
            return _scenarios()
        if args.command_name == "adapters":
            return _adapters()
        if args.command_name == "mcp-inspect":
            return _mcp_inspect(args)
        if args.command_name == "a2a-inspect":
            return _a2a_inspect(args)
        parser.error(f"unknown command: {args.command_name}")
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
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

