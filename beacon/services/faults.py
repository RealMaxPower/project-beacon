from __future__ import annotations

import copy
from typing import Any

from beacon.models import EventRecorder


class InjectedFault(RuntimeError):
    """Raised when a scenario's fault table decides this call should fail."""


class FaultTable:
    """
    Declarative, deterministic failures a scenario can ask a service for.

    Not a service. Any service composes one, so "the third call fails" is a
    thing a scenario states rather than a thing each service reimplements.

    The whole recovery family needs this. An agent that never meets a failure
    cannot be observed recovering from one, and every scenario before this
    handed the subject a world where tools always worked — which is not the
    world, and is the half of agent behaviour that never got measured.

    The mechanic worth the file is `after_effect: "applied"`: the call takes
    effect *and* reports an error. That is the failure that separates an agent
    which reconciles from one which retries blindly, and nothing in the harness
    could produce it. A retry after a clean failure is correct behaviour; a
    retry after this one double-pays, duplicates the file, or sends the message
    twice — and the agent has no way to tell the two apart except by looking.

    Every fault that fires records `fault_injected`. Without that a table which
    silently stopped matching — because a fixture was edited, or an argument
    renamed — would quietly turn a recovery scenario into a happy path, and it
    would keep passing.
    """

    def __init__(
        self, faults: list[dict[str, Any]] | None, recorder: EventRecorder
    ) -> None:
        self._faults = copy.deepcopy(faults or [])
        self._recorder = recorder
        self._seen: dict[int, int] = {}

    def reset(self) -> None:
        self._seen = {}

    def check(self, tool: str, arguments: dict[str, Any]) -> str | None:
        """
        Whether this call should fail, and what should happen if it does.

        Returns `None` to proceed, `"none"` for a clean failure, or `"applied"`
        when the caller must carry the change out and *then* raise. Callers
        that ignore the return value get a clean failure, which is the safe
        default: a service that has not thought about partial application
        should not be silently producing it.
        """
        for index, fault in enumerate(self._faults):
            if fault.get("tool") != tool:
                continue
            if not self._matches(fault.get("match", {}), arguments):
                continue

            count = self._seen.get(index, 0) + 1
            self._seen[index] = count
            when = fault.get("nth")
            if when is not None and count not in [int(n) for n in when]:
                continue

            after = str(fault.get("after_effect", "none"))
            self._recorder.record(
                "fault_injected",
                "fault_injected",
                {
                    "tool": tool,
                    "occurrence": count,
                    "error": fault.get("error", "InjectedFault"),
                    "after_effect": after,
                },
            )
            return after
        return None

    def message(self, tool: str) -> str:
        for fault in self._faults:
            if fault.get("tool") == tool:
                return str(
                    fault.get("message")
                    or f"{fault.get('error', 'InjectedFault')}: the call did not complete"
                )
        return "the call did not complete"

    @staticmethod
    def _matches(match: dict[str, Any], arguments: dict[str, Any]) -> bool:
        """
        Whether this fault is about this call.

        Deliberately small. `equals` pins an argument, `contains` looks inside
        one, and `argv_startswith` is for the shell, where the interesting unit
        is the command rather than any single field. A richer matcher would be
        a query language nobody asked for, and every rule in it would be
        another way for a scenario to stop matching without saying so.
        """
        for field, expected in match.get("equals", {}).items():
            if arguments.get(field) != expected:
                return False
        for field, needle in match.get("contains", {}).items():
            if str(needle) not in str(arguments.get(field, "")):
                return False
        prefix = match.get("argv_startswith")
        if prefix:
            argv = str(arguments.get("command", "")).split()
            if argv[: len(prefix)] != [str(token) for token in prefix]:
                return False
        return True
