#!/usr/bin/env python3
"""
Run Beacon's MCP client against real third-party MCP servers.

    python3 conformance/run_mcp_sweep.py
    python3 conformance/run_mcp_sweep.py --only everything,time --timeout 90

Unlike `tests/`, this talks to the outside world: it downloads and launches
servers other people wrote. That is the whole point. A client verified only
against the fixture in `examples/mcp_echo_server.py` proves that Beacon agrees
with itself, which is not evidence of anything.

Each target is taken through the full client surface — initialize, the
initialized notification, tools/list, and where a safe read-only call exists,
tools/call — and every outcome is recorded, including the ones that fail.
Failures here are the findings; a sweep that reports nothing wrong has usually
not run.

Exit code is 0 when every reachable target passed, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from beacon.protocols import MCPError, MCPStdioClient  # noqa: E402
from beacon.toolschema import validate_tool_name  # noqa: E402

TARGETS = json.loads((Path(__file__).parent / "mcp_targets.json").read_text())["targets"]


def _substitute(command: list[str], workspace: Path) -> list[str]:
    return [
        token.format(workspace=str(workspace), repo=str(ROOT)) for token in command
    ]


def _runtime_available(command: list[str]) -> bool:
    from shutil import which

    return which(command[0]) is not None


def probe(target: dict[str, Any], timeout: float, workspace: Path) -> dict[str, Any]:
    """Take one server through the client surface, recording whatever happens."""
    record: dict[str, Any] = {
        "id": target["id"],
        "package": target["package"],
        "reachable": False,
        "protocol_version": None,
        "server_info": {},
        "tool_count": 0,
        "tools": [],
        "unpublishable_names": [],
        "call": None,
        "errors": [],
        "seconds": 0.0,
    }
    command = _substitute(target["command"], workspace)
    if not _runtime_available(command):
        record["errors"].append(f"runtime not installed: {command[0]}")
        return record

    started = time.monotonic()
    try:
        with MCPStdioClient(command, timeout_seconds=timeout) as client:
            record["reachable"] = True
            record["protocol_version"] = client.protocol_version
            record["server_info"] = client.server_info

            tools = client.list_tools()
            record["tool_count"] = len(tools)
            record["tools"] = sorted(t.get("name", "?") for t in tools)

            # Beacon refuses to publish a name a model cannot receive. If a
            # real server ships one, that is a compatibility fact worth having
            # before a scenario depends on it.
            for tool in tools:
                try:
                    validate_tool_name(str(tool.get("name", "")))
                except Exception as exc:
                    record["unpublishable_names"].append(
                        {"name": tool.get("name"), "reason": str(exc)[:120]}
                    )

            safe = target.get("safe_call")
            if safe:
                arguments = json.loads(
                    json.dumps(safe["arguments"]).replace("{repo}", str(ROOT))
                )
                if safe["tool"] not in record["tools"]:
                    record["call"] = {
                        "tool": safe["tool"],
                        "ok": False,
                        "detail": "tool not offered by this server",
                    }
                else:
                    result = client.call_tool(safe["tool"], arguments)
                    record["call"] = {
                        "tool": safe["tool"],
                        "ok": not result.get("isError", False),
                        "detail": json.dumps(result)[:160],
                    }
    except MCPError as exc:
        record["errors"].append(f"MCPError: {exc}")
    except subprocess.SubprocessError as exc:
        record["errors"].append(f"{type(exc).__name__}: {exc}")
    except Exception as exc:  # a sweep must survive any one target
        record["errors"].append(f"{type(exc).__name__}: {exc}")
        record["traceback"] = traceback.format_exc()[-600:]
    record["seconds"] = round(time.monotonic() - started, 1)
    return record


def verdict(record: dict[str, Any]) -> str:
    if record["errors"]:
        return "ERROR"
    if not record["reachable"]:
        return "UNREACHABLE"
    if record["unpublishable_names"]:
        return "INCOMPATIBLE"
    if record["call"] and not record["call"]["ok"]:
        return "CALL FAILED"
    return "OK"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="Comma-separated target ids.")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)

    selected = TARGETS
    if args.only:
        wanted = {item.strip() for item in args.only.split(",")}
        selected = [t for t in TARGETS if t["id"] in wanted]

    workspace = ROOT / ".beacon" / "conformance-workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    print(f"Beacon MCP conformance sweep — {len(selected)} third-party server(s)\n")
    records = []
    for target in selected:
        print(f"  {target['id']:<22} ", end="", flush=True)
        record = probe(target, args.timeout, workspace)
        records.append(record)
        state = verdict(record)
        detail = (
            f"{record['tool_count']} tools"
            if record["reachable"]
            else (record["errors"][0][:60] if record["errors"] else "")
        )
        print(f"{state:<13} {record['seconds']:>5.1f}s  {detail}")

    print()
    counts: dict[str, int] = {}
    for record in records:
        counts[verdict(record)] = counts.get(verdict(record), 0) + 1
    print("  " + "  ".join(f"{state}={n}" for state, n in sorted(counts.items())))

    problems = [r for r in records if verdict(r) not in {"OK", "UNREACHABLE"}]
    if problems:
        print("\nFindings:")
        for record in problems:
            print(f"\n  {record['id']} — {verdict(record)}")
            for error in record["errors"]:
                print(f"    error: {error}")
            for bad in record["unpublishable_names"]:
                print(f"    unpublishable tool name: {bad['name']!r}")
            if record["call"] and not record["call"]["ok"]:
                print(f"    call {record['call']['tool']}: {record['call']['detail']}")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps({"targets": records}, indent=2) + "\n", encoding="utf-8"
        )
        print(f"\nWrote {args.json_out}")

    reachable = [r for r in records if r["reachable"]]
    passed = [r for r in reachable if verdict(r) == "OK"]
    print(f"\n{len(passed)}/{len(reachable)} reachable servers fully OK.")
    return 0 if len(passed) == len(reachable) and reachable else 1


if __name__ == "__main__":
    raise SystemExit(main())
