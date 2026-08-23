from __future__ import annotations

"""The commands that execute a scenario: `run` and `serve-mcp`."""

import argparse
import os
from typing import Sequence

from beacon.adapters import (
    A2ASubjectAdapter,
    JSONLCommandAdapter,
    MCPHostAdapter,
    MCPServeAdapter,
    MCPToolSubjectAdapter,
    ReferenceInboxAdapter,
)
from beacon.baseline import (
    build_baseline,
    compare_to_baseline,
    load_baseline,
    load_recent_evidence,
    save_baseline,
)
from beacon.builtins import resolve_scenario
from beacon.cliargs import split_command
from beacon.determinism import compare_runs, repeat_run_ids
from beacon.models import Evidence, Scenario, ScenarioError
from beacon.protocols import MINIMUM_TOKEN_LENGTH
from beacon.runner import run_scenario
from beacon.secrets import looks_like_a_secret
from beacon.services import import_service_module


def report_baseline(
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


def run(args: argparse.Namespace) -> int:
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
    elif args.adapter == "mcp-tool":
        if not args.mcp_url:
            raise ScenarioError("--adapter mcp-tool requires --mcp-url")
        if not args.tool:
            raise ScenarioError("--adapter mcp-tool requires --tool")
        if args.command:
            raise ScenarioError(
                "--command applies to adapters that launch a process; an MCP "
                "tool subject is a service someone else is already running"
            )
        if args.env_passthrough or args.env_secret:
            # Beacon starts nothing here, so an environment option would be a
            # flag that silently does nothing to the subject — and the operator
            # would believe a credential had been passed.
            raise ScenarioError(
                "environment options apply to adapters that launch a process; "
                "use --authorization to authenticate to an MCP server"
            )
        adapter = MCPToolSubjectAdapter(
            args.mcp_url,
            args.tool,
            args.arguments,
            timeout_seconds=args.timeout,
            authorization=args.authorization,
            **({"artifact_name": args.artifact_name} if args.artifact_name else {}),
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

    regressed = report_baseline(args, evidences)

    stable = args.repeat == 1 or compare_runs(evidences).stable
    passed = all(evidence.result == "PASS" for evidence in evidences)
    return 0 if passed and stable and not regressed else 1


def serve_mcp(args: argparse.Namespace) -> int:
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
        # Checked here as well as in `MCPHTTPService`, so a weak token is
        # refused by name and before a run directory exists, rather than as an
        # anonymous ValueError from inside a run that has already started.
        if len(token) < MINIMUM_TOKEN_LENGTH:
            raise ScenarioError(
                f"{args.token_env} holds {len(token)} characters; a bearer "
                f"token guarding the tool façade needs at least "
                f"{MINIMUM_TOKEN_LENGTH}. `python3 -c 'import secrets; "
                f"print(secrets.token_urlsafe(32))'` prints a usable one."
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
