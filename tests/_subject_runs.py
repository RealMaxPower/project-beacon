from __future__ import annotations

import atexit
import functools
import os
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Iterable

from beacon.adapters import JSONLCommandAdapter
from beacon.models import Scenario
from beacon.runner import run_scenario


ROOT = Path(__file__).resolve().parents[1]


"""
Run each adversarial subject once, and let every harness share the answer.

Three test modules ask questions of the same forty-seven subjects — which
assertions did this one fail, what verdict did it produce, did it write a
bundle at all — and each was spawning its own subprocess to find out.
`test_adversarial_subjects` alone ran every subject twice, from two tests that
make the identical call and assert on different fields of the same outcome.

The subjects are deterministic by construction and `tests/test_determinism.py`
proves the runner is, so the re-runs bought nothing but wall-clock. At the ~330
manifest entries a 55-scenario suite implies, the duplication is the difference
between a suite that takes two minutes and one that takes eight.

Evidence directories live for the process rather than for one test, because a
caller that wants to check a bundle exists needs it to still be there. One
temporary directory, removed at exit.
"""


@functools.lru_cache(maxsize=1)
def _evidence_root() -> str:
    directory = tempfile.TemporaryDirectory(prefix="beacon-subject-runs-")
    atexit.register(directory.cleanup)
    return directory.name


_spawned = 0
_spawn_lock = threading.Lock()
"""
Every run this process has started, counted once and never reset.

Serves two purposes and has to be independent of the cache for both. It makes
each run id unique, because the runner refuses to write into a directory that
already exists — rightly, since overwriting a bundle is how evidence stops
being evidence — and two cache entries differing only in timeout would
otherwise choose the same path. And it is what `runs_performed` reports, which
has to keep counting across a `cache_clear`, or the budget guard would be
satisfied by the very thing it exists to catch.

A plain integer rather than a counter object, because reading it must not
advance it: the first version used `itertools.count` and every call to
`runs_performed` consumed a value, so asking how many runs had happened made
one more happen.
"""


@functools.lru_cache(maxsize=None)
def _run(
    script: str,
    scenario_path: str,
    timeout: float | None,
    label: str,
    args: tuple[str, ...] = (),
) -> Any:
    global _spawned
    with _spawn_lock:
        _spawned += 1
        run_id = f"{label}-{_spawned:03d}"
    return run_scenario(
        Scenario.load(Path(scenario_path)),
        JSONLCommandAdapter(
            [sys.executable, str(ROOT / script), *args],
            timeout_seconds=timeout,
        ),
        output_dir=_evidence_root(),
        run_id=run_id,
    )


def run_subject(case: dict[str, Any], scenario_path: Path) -> Any:
    """
    This subject's run against this scenario, from cache after the first ask.

    The manifest's `timeout_seconds` is honoured, and only where it is asked
    for. A blanket default would override every scenario's declared budget and
    record a `limits_overridden` event on every run, which is a change to what
    the evidence says rather than a speed-up — and it is what the two callers
    used to disagree about, one passing 15 seconds and one passing nothing.

    The run id carries the scenario as well as the subject, because one script
    now serves several scenarios and they share an output directory.
    """
    override = case.get("timeout_seconds")
    return _run(
        case["script"],
        str(scenario_path),
        None if override is None else float(override),
        f"{case['id']}--{Path(scenario_path).parent.name}",
        tuple(subject_args(case)),
    )


def subject_args(case: dict[str, Any]) -> list[str]:
    """
    The arguments a manifest entry launches its script with.

    `breaker.py` is one script serving many entries, so it needs to be told
    which one it is. Everything else takes no arguments and is unaffected.
    """
    if case.get("args") is not None:
        return [str(item) for item in case["args"]]
    if Path(case["script"]).name == "breaker.py":
        return [case["id"]]
    return []


def failed_assertions(case: dict[str, Any], scenario_path: Path) -> set[str]:
    """Which assertions this subject actually makes fail."""
    outcome = run_subject(case, scenario_path)
    return {
        item["id"] for item in outcome.evidence.assertions if not item["passed"]
    }


def warm(cases: Iterable[tuple[dict[str, Any], Path]]) -> None:
    """
    Run a batch concurrently, so later calls are cache hits.

    Worth doing because the suite is bound almost entirely on waiting for
    subprocesses — it sits at a few percent CPU while spawning a hundred
    Pythons one at a time. Threads rather than processes: the payload already
    *is* process spawning, and `spawn` on macOS and Windows would add the cost
    this is trying to remove.

    Safe because nothing in `beacon/` changes global state during a run —
    there is no `os.chdir`, the service registry is written once at import, and
    each run builds its own recorder, services and output directory.

    Timing-sensitive subjects run first and alone. A subject that exists to
    exhaust a four-second budget is measuring elapsed time, and on an
    oversubscribed runner a thread pool is exactly what makes elapsed time
    unpredictable.
    """
    batch = list(cases)
    timed = [item for item in batch if "timeout_seconds" in item[0]]
    rest = [item for item in batch if "timeout_seconds" not in item[0]]

    for case, path in timed:
        run_subject(case, path)

    if not rest:
        return
    workers = int(os.environ.get("BEACON_TEST_WORKERS") or min(8, (os.cpu_count() or 2)))
    if workers <= 1:
        for case, path in rest:
            run_subject(case, path)
        return
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in [pool.submit(run_subject, case, path) for case, path in rest]:
            future.result()


def runs_performed() -> int:
    """
    How many subject runs this process has actually spawned.

    Read by `tests/test_suite_budget.py`. The invariant it guards — one run per
    subject, however many harnesses ask — is invisible when it breaks: a fifth
    harness that spawns everything again shows up as CI being slow, months
    later, with nothing pointing at the change that did it.
    """
    return _spawned
