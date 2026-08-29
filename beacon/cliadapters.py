from __future__ import annotations

"""
The adapter table, and the listing built from it.

Split out of `cli.py` so that `cliargs.py` can read `RUN_ADAPTERS` for its
`--adapter` choices without importing the module that imports it. Nothing here
knows about argparse: this is the catalogue, and the parser and the `adapters`
command are both readers of it.
"""

from dataclasses import dataclass
from typing import Any, Callable

from beacon.adapters import (
    A2ASubjectAdapter,
    JSONLCommandAdapter,
    MCPHostAdapter,
    MCPServeAdapter,
    MCPToolSubjectAdapter,
    ReferenceInboxAdapter,
)


@dataclass(frozen=True)
class AdapterSpec:
    """
    One row of `project-beacon adapters`, and the only source of `--adapter`.

    This used to be written out by hand in three places — the `choices` tuple,
    the dispatch in `_run`, and the listing — and they drifted in both
    directions at once. The listing advertised `mcp-serve`, `mcp-stdio` and
    `a2a-http`, none of which are `--adapter` values, while `mcp-tool`, a
    finished adapter exported from `beacon.adapters`, appeared in none of the
    three and could only be reached by writing Python.

    `integration_level` and the subject id are read from the adapter's own
    `descriptor` rather than retyped here, because those two are what the
    evidence bundle will say and a copy of them can be wrong. The rest is
    prose, and a descriptor has no business carrying prose: it would end up in
    every bundle Beacon writes.

    `probe` builds a throwaway instance purely to read that descriptor. Every
    adapter's `__init__` is plain assignment — no I/O, no process, no socket —
    and `tests/test_cli_adapters.py` fails if that stops being true.
    """

    flag: str
    subject: str
    interface: str
    status: str
    reached_by: str
    probe: Callable[[], Any] | None = None
    level: int | None = None


ADAPTERS: tuple[AdapterSpec, ...] = (
    AdapterSpec(
        flag="reference",
        subject="Beacon reference inbox agent",
        interface="in-process",
        status="MVP",
        reached_by="beacon run --adapter reference",
        probe=ReferenceInboxAdapter,
    ),
    AdapterSpec(
        flag="command",
        subject="Any wrapped CLI/API/SDK agent",
        interface="bidirectional JSONL",
        status="MVP",
        reached_by="beacon run --adapter command",
        probe=lambda: JSONLCommandAdapter(["true"]),
    ),
    AdapterSpec(
        flag="mcp-host",
        subject="Any MCP-speaking agent host",
        interface="Beacon serves MCP over HTTP; adapter owns lifecycle",
        status="MVP",
        reached_by="beacon run --adapter mcp-host",
        probe=lambda: MCPHostAdapter(["true"]),
    ),
    AdapterSpec(
        flag="mcp-tool",
        subject="One tool on a hosted MCP server",
        interface="Beacon calls the server; the tool is the subject",
        status="MVP",
        reached_by="beacon run --adapter mcp-tool",
        probe=lambda: MCPToolSubjectAdapter("https://example.invalid/mcp", "ask", {}),
    ),
    AdapterSpec(
        flag="a2a",
        subject="A2A agent",
        interface="A2A v1.0 HTTP+JSON or JSON-RPC",
        status="discover/send spike",
        reached_by="beacon run --adapter a2a",
        probe=lambda: A2ASubjectAdapter("https://example.invalid"),
    ),
    AdapterSpec(
        flag="mcp-serve",
        subject="An MCP host you connect yourself",
        interface="Beacon serves MCP over HTTP and waits",
        status="MVP",
        reached_by="beacon serve-mcp",
        probe=MCPServeAdapter,
    ),
    # The last two are protocol clients, not subject adapters. They have no
    # descriptor because nothing about them reaches an evidence bundle — they
    # inspect a server, they do not grade one — and `reached_by` is the column
    # that stops them being read as `--adapter` values again.
    AdapterSpec(
        flag="mcp-stdio",
        subject="MCP server",
        interface="MCP stdio client",
        status="inspect/call",
        reached_by="beacon mcp-inspect",
        level=1,
    ),
    AdapterSpec(
        flag="a2a-http",
        subject="A2A agent",
        interface="A2A Agent Card discovery",
        status="inspect",
        reached_by="beacon a2a-inspect",
        level=2,
    ),
)

RUN_ADAPTERS: tuple[AdapterSpec, ...] = tuple(
    spec for spec in ADAPTERS if spec.reached_by.startswith("beacon run ")
)


def adapter_rows() -> list[dict[str, Any]]:
    """Build the listing, reading from each adapter what the adapter knows."""
    rows: list[dict[str, Any]] = []
    for spec in ADAPTERS:
        row: dict[str, Any] = {
            "id": spec.flag,
            "subject": spec.subject,
            "interface": spec.interface,
            "reached_by": spec.reached_by,
            "status": spec.status,
        }
        if spec.probe is not None:
            descriptor = spec.probe().descriptor
            row["level"] = descriptor["integration_level"]
            row["subject_id"] = descriptor["id"]
        else:
            row["level"] = spec.level
        rows.append(row)
    return rows
