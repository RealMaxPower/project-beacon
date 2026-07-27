from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SyntheticService(Protocol):
    """
    What a scenario's simulated environment must provide.

    `docs/architecture.md` has described this contract since the first commit —
    machine-readable tool definitions, a deterministic call implementation, a
    complete state snapshot, and an exact reset — but it existed only as prose
    and duck typing. Writing it down as a Protocol makes the four requirements
    checkable, and makes it obvious what a contributor has to implement.

    Snapshot and reset carry the weight. Every verdict is a diff between two
    snapshots, and a service whose reset is not exact silently corrupts the
    next run in a repeat.
    """

    def definitions(self) -> tuple[dict[str, Any], ...]:
        """MCP-shaped tool definitions: name, description, inputSchema."""

    def call(self, tool: str, arguments: dict[str, Any]) -> Any:
        """Execute one tool call deterministically."""

    def snapshot(self) -> dict[str, Any]:
        """A complete, JSON-serialisable copy of current state."""

    def reset(self) -> None:
        """Restore the seed state exactly."""
