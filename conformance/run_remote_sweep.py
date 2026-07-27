#!/usr/bin/env python3
"""
Survey hosted MCP servers from the official registry with Beacon's client.

    python3 conformance/run_remote_sweep.py --count 50
    python3 conformance/run_remote_sweep.py --count 25 --report assessment.md

These are other people's running services, so the sweep is deliberately
cheap and polite: one `initialize` and one `tools/list` per server, no tool
calls at all, a bounded number of connections at a time, a short timeout, and
a User-Agent that says who is calling. Reading a stranger's tool manifest
costs them one request; calling their tools would cost them money and could
have side effects.

Sampling is deterministic — the registry is sorted and strided — so a rerun
covers the same servers and results are comparable.

What comes out is a compatibility survey rather than a pass/fail gate: which
protocol versions are live, which transports servers actually answer with, how
many require authentication, and how many publish tool names that cannot be
forwarded to a model.
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import threading
import time
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from beacon.protocols import MCPError, MCPHTTPClient  # noqa: E402
from beacon.toolschema import TOOL_NAME_PATTERN  # noqa: E402

REGISTRY = "https://registry.modelcontextprotocol.io/v0/servers?limit=100"
_throttle = threading.Semaphore(6)


def _ssl_context() -> ssl.SSLContext | None:
    paths = ssl.get_default_verify_paths()
    if paths.cafile or paths.capath:
        return None
    try:
        import certifi
    except ImportError:
        return None
    return ssl.create_default_context(cafile=certifi.where())


def fetch_registry(max_pages: int = 12) -> list[dict[str, Any]]:
    servers: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(max_pages):
        url = REGISTRY + (f"&cursor={cursor}" if cursor else "")
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "project-beacon/0.1", "Accept": "application/json"},
        )
        with urllib.request.urlopen(
            request, timeout=30, context=_ssl_context()
        ) as response:
            page = json.load(response)
        servers.extend(entry["server"] for entry in page.get("servers", []))
        cursor = (page.get("metadata") or {}).get("nextCursor")
        if not cursor:
            break
    return servers


def candidates(servers: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    """Deduplicate by endpoint, then stride so the sample spans the registry."""
    seen: dict[str, dict[str, Any]] = {}
    for server in servers:
        for remote in server.get("remotes") or []:
            url = remote.get("url")
            if not url or url in seen:
                continue
            if remote.get("type") not in {"streamable-http", "sse"}:
                continue
            seen[url] = {
                "name": server.get("name", "?"),
                "description": (server.get("description") or "")[:100],
                "url": url,
                "declared_transport": remote.get("type"),
            }
    ordered = [seen[url] for url in sorted(seen)]
    if count >= len(ordered):
        return ordered
    stride = len(ordered) / count
    return [ordered[int(index * stride)] for index in range(count)]


def probe(target: dict[str, Any], timeout: float) -> dict[str, Any]:
    record = dict(target)
    record.update(
        {
            "outcome": "error",
            "detail": "",
            "protocol_version": None,
            "server_name": None,
            "tool_count": 0,
            "unpublishable_tools": [],
            "seconds": 0.0,
        }
    )
    started = time.monotonic()
    with _throttle:
        try:
            client = MCPHTTPClient(target["url"], timeout_seconds=timeout)
            client.start()
            record["protocol_version"] = client.protocol_version
            record["server_name"] = client.server_info.get("name")
            tools = client.list_tools()
            record["tool_count"] = len(tools)
            record["unpublishable_tools"] = [
                tool.get("name")
                for tool in tools
                if not TOOL_NAME_PATTERN.match(str(tool.get("name", "")))
            ]
            record["outcome"] = "ok"
        except MCPError as exc:
            message = str(exc)
            record["detail"] = message[:160]
            lowered = message.lower()
            if "http 401" in lowered or "http 403" in lowered:
                record["outcome"] = "auth-required"
            elif "http 404" in lowered or "http 405" in lowered:
                record["outcome"] = "wrong-endpoint"
            elif "could not reach" in lowered or "timed out" in lowered:
                record["outcome"] = "unreachable"
            else:
                record["outcome"] = "protocol-error"
        except Exception as exc:
            record["detail"] = f"{type(exc).__name__}: {exc}"[:160]
    record["seconds"] = round(time.monotonic() - started, 1)
    return record


def render(records: list[dict[str, Any]]) -> str:
    outcomes = Counter(r["outcome"] for r in records)
    ok = [r for r in records if r["outcome"] == "ok"]
    versions = Counter(r["protocol_version"] for r in ok)
    offenders = [r for r in ok if r["unpublishable_tools"]]
    total_tools = sum(r["tool_count"] for r in ok)

    lines = [
        "# Hosted MCP server survey",
        "",
        f"Beacon's MCP client against {len(records)} hosted servers drawn from the "
        "official registry. One `initialize` and one `tools/list` each; no tool "
        "calls were made.",
        "",
        "## Reachability",
        "",
        "| Outcome | Servers |",
        "|---|---|",
    ]
    for outcome, n in outcomes.most_common():
        lines.append(f"| {outcome} | {n} |")
    lines += [
        "",
        f"{len(ok)} of {len(records)} completed the handshake and returned a tool "
        f"list, exposing {total_tools} tools in total.",
        "",
        "## Protocol versions negotiated",
        "",
        "| Version | Servers |",
        "|---|---|",
    ]
    for version, n in versions.most_common():
        lines.append(f"| {version} | {n} |")

    lines += [
        "",
        "## Tool names that cannot be forwarded to a model",
        "",
        f"Names must match `{TOOL_NAME_PATTERN.pattern}` to be published in an "
        "API `tools` parameter. Servers shipping names outside it cannot be "
        "relayed to a model without renaming.",
        "",
    ]
    if offenders:
        lines += ["| Server | Offending names |", "|---|---|"]
        for record in offenders:
            names = ", ".join(f"`{n}`" for n in record["unpublishable_tools"][:4])
            lines.append(f"| {record['name']} | {names} |")
    else:
        lines.append("None found in this sample.")

    slow = sorted(ok, key=lambda r: -r["seconds"])[:5]
    lines += ["", "## Slowest handshakes", "", "| Server | Seconds | Tools |", "|---|---|---|"]
    for record in slow:
        lines.append(
            f"| {record['name']} | {record['seconds']} | {record['tool_count']} |"
        )

    failures = [r for r in records if r["outcome"] not in {"ok", "auth-required"}]
    if failures:
        lines += ["", "## Failures worth reading", "", "| Server | Outcome | Detail |", "|---|---|---|"]
        for record in failures[:20]:
            detail = record["detail"].replace("|", "\\|")[:110]
            lines.append(
                f"| {record['name']} | {record['outcome']} | {detail} |"
            )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)

    print("Fetching the official MCP registry…")
    servers = fetch_registry()
    targets = candidates(servers, args.count)
    print(f"{len(servers)} registry entries → probing {len(targets)} unique endpoints\n")

    records: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for record in pool.map(lambda t: probe(t, args.timeout), targets):
            records.append(record)
            mark = {"ok": "OK", "auth-required": "AUTH"}.get(
                record["outcome"], record["outcome"].upper()
            )
            print(
                f"  {mark:<15} {record['name'][:38]:<38} "
                f"{record['seconds']:>5.1f}s  "
                f"{record['tool_count'] if record['outcome'] == 'ok' else record['detail'][:44]}"
            )

    print()
    for outcome, n in Counter(r["outcome"] for r in records).most_common():
        print(f"  {outcome:<16} {n}")

    report = render(records)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report, encoding="utf-8")
        print(f"\nWrote {args.report}")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
