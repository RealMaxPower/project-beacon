from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


class UsageLimitExceeded(RuntimeError):
    """Raised when a run exceeds its declared call or wall-clock budget."""


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

    def summary(self) -> dict[str, Any]:
        seconds = [call.seconds for call in self._calls]
        failed = [call for call in self._calls if not call.ok]
        return {
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
