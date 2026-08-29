from __future__ import annotations

import threading
import time
import unittest
from typing import Any
from unittest import mock

import beacon.models as models
from beacon.models import EventRecorder
from beacon.protocols.mcp_server import _InFlight
from beacon.services import ToolRouter


class _CountingService:
    """A service whose only job is to be called from many threads at once."""

    def __init__(self, delay: float = 0.0) -> None:
        self._delay = delay

    def definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "probe_touch",
                "description": "Records a call and returns.",
                "inputSchema": {"type": "object", "properties": {}},
            }
        ]

    def call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self._delay:
            time.sleep(self._delay)
        return {"ok": True}

    def snapshot(self) -> dict[str, Any]:
        return {}

    def reset(self) -> None:
        return None


def _in_parallel(work, count: int) -> None:
    """Run `work(i)` on `count` threads released together by a barrier."""
    ready = threading.Barrier(count)

    def run(index: int) -> None:
        ready.wait()
        work(index)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)


class EventSequenceTests(unittest.TestCase):
    """
    Sequence numbers are the evidence log's only ordering, and `event_order`
    grades on them.

    `record` read the list length, built an `Event` — calling `utc_now()` on the
    way — and only then appended. Two threads inside that window take the same
    number. The façade serves one thread per request and real MCP hosts issue
    parallel tool calls, so this needs no adversarial subject: it is what an
    ordinary run against Claude Desktop or Cursor can produce.
    """

    THREADS = 24

    def _slow_clock(self):
        """
        `utc_now`, delayed, so the window between the length read and the
        append is wide enough to land in reliably.

        Without this the test passes against the unfixed code: the GIL makes the
        real window narrow enough that forty threads will not collide, and a
        concurrency test that never reproduces the race is a description of the
        fix rather than a check on it. Measured — unpatched, this test passes
        before and after; patched, it fails before and passes after. In the fixed
        code the clock is called inside the lock, so the delay serialises the
        writers instead of tearing them.
        """

        def slow() -> Any:
            time.sleep(0.002)
            return models.datetime.now(models.timezone.utc)

        return mock.patch.object(models, "utc_now", slow)

    def test_concurrent_records_take_distinct_sequence_numbers(self) -> None:
        recorder = EventRecorder()
        with self._slow_clock():
            _in_parallel(
                lambda i: recorder.record("tool_call", f"t-{i}", {}), self.THREADS
            )

        sequences = [event.sequence for event in recorder.events]
        self.assertEqual(len(sequences), self.THREADS, "an event was lost")
        self.assertEqual(
            sorted(sequences),
            list(range(1, self.THREADS + 1)),
            "sequence numbers are not 1..N exactly once — two events shared one, "
            "which is a wrong answer to any event_order assertion over them",
        )

    def test_every_recorded_event_survives(self) -> None:
        """A lost append is the same defect seen from the other side."""
        recorder = EventRecorder()
        with self._slow_clock():
            _in_parallel(
                lambda i: recorder.record("tool_call", f"t-{i}", {}), self.THREADS
            )
        self.assertEqual(
            {event.target for event in recorder.events},
            {f"t-{i}" for i in range(self.THREADS)},
        )


class ToolBudgetTests(unittest.TestCase):
    """
    `max_tool_calls` is published to the subject as a limit it was told about,
    so a limit that admits more than it says is a number the bundle reports
    rather than a budget the run kept.

    **These pass without the lock, and are kept anyway.** `self._calls += 1` is
    a read, an add and a write, and the language does not promise they are one
    step — but under CPython's GIL the interleaving is rare enough that this did
    not reproduce across repeated runs at a microsecond switch interval, with
    the arrival window widened. So this is an invariant guard, not proof of a
    fix, and saying otherwise would be the exact overstatement `beacon prove`
    exists to catch elsewhere in this repository.

    The lock is still right. The GIL is an implementation detail, not a
    guarantee, and the free-threaded build shipping since 3.13 removes it — on
    that interpreter the race is ordinary rather than exotic.
    """

    BUDGET = 8
    ATTEMPTS = 40

    def _router(self) -> ToolRouter:
        router = ToolRouter(EventRecorder(), max_tool_calls=self.BUDGET)
        router.register(_CountingService())
        return router

    def test_the_budget_is_not_overspent_under_concurrency(self) -> None:
        router = self._router()
        allowed: list[int] = []
        guard = threading.Lock()

        def attempt(index: int) -> None:
            try:
                router.call("probe_touch", {}, call_id=f"c-{index}")
            except RuntimeError:
                return
            with guard:
                allowed.append(index)

        _in_parallel(attempt, self.ATTEMPTS)
        self.assertEqual(
            len(allowed),
            self.BUDGET,
            f"{len(allowed)} calls succeeded against a budget of {self.BUDGET}",
        )

    def test_the_refusal_still_arrives_as_a_tool_result(self) -> None:
        """The budget stays soft: refusing is not killing the run."""
        router = self._router()
        with self.assertRaises(RuntimeError) as caught:
            for index in range(self.BUDGET + 1):
                router.call("probe_touch", {}, call_id=f"c-{index}")
        self.assertIn("budget", str(caught.exception))

    def test_the_exhaustion_event_reports_this_call_s_own_count(self) -> None:
        """
        The count in the event is the one this call was given, not a re-read of
        a counter another thread may have moved since.
        """
        recorder = EventRecorder()
        router = ToolRouter(recorder, max_tool_calls=1)
        router.register(_CountingService())
        router.call("probe_touch", {}, call_id="first")
        with self.assertRaises(RuntimeError):
            router.call("probe_touch", {}, call_id="second")
        exhausted = [e for e in recorder.events if e.kind == "tool_budget_exhausted"]
        self.assertEqual(len(exhausted), 1)
        self.assertEqual(exhausted[0].payload["calls"], 2)


class ShutdownDrainTests(unittest.TestCase):
    """
    `shutdown()` stops the accept loop; it does not wait for the handlers
    already inside it, and `daemon_threads` means `server_close()` will not
    either. A tool call still running while the runner snapshots the after-state
    is a torn read of the thing the run exists to record.
    """

    def test_drain_waits_for_a_request_that_is_still_running(self) -> None:
        inflight = _InFlight()
        entered = threading.Event()
        release = threading.Event()

        def handler() -> None:
            with inflight:
                entered.set()
                release.wait(timeout=10)

        worker = threading.Thread(target=handler)
        worker.start()
        self.assertTrue(entered.wait(timeout=10))

        self.assertFalse(
            inflight.drain(timeout=0.2),
            "drain reported success while a handler was still inside",
        )
        release.set()
        worker.join(timeout=10)
        self.assertTrue(inflight.drain(timeout=5), "drain never saw the handler leave")

    def test_drain_gives_up_rather_than_hanging_the_harness(self) -> None:
        """
        The bound is the point. The party on the other end is the one being
        graded, and a handler that never returns must not take the run with it —
        the drain expires, and the caller records a limitation instead.
        """
        inflight = _InFlight()
        started = threading.Event()

        def never_returns() -> None:
            with inflight:
                started.set()
                threading.Event().wait(timeout=30)

        worker = threading.Thread(target=never_returns, daemon=True)
        worker.start()
        self.assertTrue(started.wait(timeout=10))
        self.assertFalse(inflight.drain(timeout=0.2))

    def test_an_idle_service_drains_immediately(self) -> None:
        self.assertTrue(_InFlight().drain(timeout=0.01))

    def test_the_count_returns_to_zero_after_a_handler_raises(self) -> None:
        """An exception inside a handler must not leave the façade undrainable."""
        inflight = _InFlight()

        def boom() -> None:
            with self.assertRaises(ValueError):
                with inflight:
                    raise ValueError("handler failed")

        boom()
        self.assertTrue(inflight.drain(timeout=1))


if __name__ == "__main__":
    unittest.main()
