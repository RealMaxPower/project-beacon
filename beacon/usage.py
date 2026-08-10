from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


class UsageLimitExceeded(RuntimeError):
    """Raised when a run exceeds its declared call or wall-clock budget."""


# Numeric fields summed across everything a subject reports. Anything else it
# sends is kept verbatim per source rather than aggregated, because adding up
# numbers whose meaning is not agreed is how a total becomes fiction.
REPORTED_TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_creation_tokens",
    "total_tokens",
)

REPORTED_NOTICE = (
    "Token and cost figures under `usage.reported` were supplied by the "
    "subject. Beacon did not observe them and cannot check them: that spend "
    "happened inside the subject's own infrastructure, on its own credentials. "
    "Treat them as a claim of the same kind as the answer being graded."
)


@dataclass
class Call:
    kind: str
    target: str
    seconds: float
    ok: bool
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "target": self.target,
            "seconds": round(self.seconds, 3),
            "ok": self.ok,
            "detail": self.detail,
        }


class UsageRecorder:
    """
    Counts what a run spends on the subject's side.

    Beacon cannot see a remote agent's token usage — that spend happens inside
    someone else's infrastructure, on their model credentials. What it can
    measure is what it caused: how many requests were made, how long each took,
    and how many failed. Those are the numbers that bound a run.

    A subject may volunteer what it spent, and `report` keeps that in a separate
    part of the summary. The separation is the point. Everything else here is
    something Beacon watched happen; a reported token count is a claim by the
    party under evaluation, and a bundle that presented the two as one kind of
    number would be overstating what it knows.

    `max_calls` is a real ceiling rather than a report. A scenario that declares
    one gets it enforced, so an agent that loops cannot quietly run up a bill
    on the other side while Beacon watches.

    It binds only where Beacon drives the subject — the A2A and MCP-tool
    adapters, which make the requests themselves. A command or MCP-host subject
    drives itself and is bounded by `timeout_seconds` and
    `max_protocol_messages` instead, so declaring `max_subject_calls` on a
    scenario written for one of those buys nothing. `injection-resistance`
    declared one that never fired, and `docs/running-it-yourself.md` cited it
    as the guard against a runaway model bill on a command subject, where it
    does not apply.
    """

    def __init__(
        self,
        *,
        max_calls: int | None = None,
        max_seconds: float | None = None,
    ) -> None:
        self._calls: list[Call] = []
        self._reported: list[dict[str, Any]] = []
        self._max_calls = max_calls
        self._max_seconds = max_seconds

    @property
    def calls(self) -> tuple[Call, ...]:
        return tuple(self._calls)

    @property
    def call_count(self) -> int:
        return len(self._calls)

    @property
    def total_seconds(self) -> float:
        return sum(call.seconds for call in self._calls)

    def check(self) -> None:
        """Raise if the next call would exceed the budget."""
        if self._max_calls is not None and len(self._calls) >= self._max_calls:
            raise UsageLimitExceeded(
                f"run reached its budget of {self._max_calls} subject calls"
            )
        if self._max_seconds is not None and self.total_seconds >= self._max_seconds:
            raise UsageLimitExceeded(
                f"run reached its budget of {self._max_seconds:g}s of subject time"
            )

    def record(
        self,
        kind: str,
        target: str,
        seconds: float,
        *,
        ok: bool = True,
        **detail: Any,
    ) -> Call:
        call = Call(kind=kind, target=target, seconds=seconds, ok=ok, detail=detail)
        self._calls.append(call)
        return call

    def timed(self, kind: str, target: str) -> "_Timer":
        """Context manager that checks the budget, then times the call."""
        self.check()
        return _Timer(self, kind, target)

    def report(self, source: str, usage: Any) -> bool:
        """
        Record what the subject says it spent. Returns whether anything landed.

        Kept apart from `record` on purpose, and surfaced under a different key.
        A call Beacon made is something it watched happen; a token count is a
        number the subject sent, and the subject is the thing under evaluation.
        Merging them would put an unverified figure into the same field as a
        measurement, which is the shape of overstatement this project exists to
        catch — and it would do it in the bundle rather than in prose, where it
        is harder to notice and easier to quote.

        Nothing here validates the numbers, because nothing can. It only refuses
        what it cannot represent.
        """
        if not isinstance(usage, dict) or not usage:
            return False
        entry: dict[str, Any] = {"source": source}
        for key, value in usage.items():
            if not isinstance(key, str):
                continue
            if isinstance(value, bool):
                # `True` is an int in Python and would silently add 1 to a
                # token total. A flag is not a count.
                entry[key] = value
            elif isinstance(value, (int, float, str)):
                entry[key] = value
        if len(entry) == 1:
            return False
        self._reported.append(entry)
        return True

    @property
    def reported(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._reported)

    def _reported_summary(self) -> dict[str, Any]:
        totals: dict[str, int | float] = {}
        for entry in self._reported:
            for name in REPORTED_TOKEN_FIELDS:
                value = entry.get(name)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    continue
                totals[name] = totals.get(name, 0) + value
        return {
            "note": REPORTED_NOTICE,
            "totals": totals,
            "entries": list(self._reported),
        }

    def summary(self) -> dict[str, Any]:
        seconds = [call.seconds for call in self._calls]
        failed = [call for call in self._calls if not call.ok]
        summary: dict[str, Any] = {
            "calls": len(self._calls),
            "failed_calls": len(failed),
            "total_seconds": round(self.total_seconds, 3),
            "slowest_seconds": round(max(seconds), 3) if seconds else 0.0,
            "budget": {
                "max_calls": self._max_calls,
                "max_seconds": self._max_seconds,
            },
            "detail": [call.to_dict() for call in self._calls],
        }
        # Present only when the subject said something, so an absent key means
        # "nothing was reported" rather than "reported zero". A run that spent
        # money and a run that spent none must not read the same.
        if self._reported:
            summary["reported"] = self._reported_summary()
        return summary


class _Timer:
    def __init__(self, recorder: UsageRecorder, kind: str, target: str) -> None:
        self._recorder = recorder
        self._kind = kind
        self._target = target
        self._started = 0.0
        self.detail: dict[str, Any] = {}
        self.ok = True

    def __enter__(self) -> "_Timer":
        self._started = time.monotonic()
        return self

    def __exit__(self, exc_type: Any, *_: Any) -> None:
        self._recorder.record(
            self._kind,
            self._target,
            time.monotonic() - self._started,
            ok=self.ok and exc_type is None,
            **self.detail,
        )
