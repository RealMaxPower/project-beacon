"""
A subject expressed as data: what it will do, and what it will answer.

Forty-seven hand-written subjects for seven scenarios is roughly six per
scenario, and every one of them is the same shape — one competent baseline plus
exactly one perturbation. `attempts_send` is the briefing baseline plus "append
send calls". `skips_tagging` is the organise loop minus the tag calls.
`malformed_summary` is the summary with four fields edited. The baselines are
genuinely different from each other; the perturbations are not.

So the baselines stay code, one per scenario, written by whoever writes the
scenario. The perturbations become data. A plan module does its read-only
discovery eagerly — it has to, to know what to do — and returns the mutating
actions and the answer for a strategy in `_strategies.py` to transform before
anything is executed.

The strategy is a pure function over a plan. Execution is real: real tool
calls, real artifact, real completion. Nothing here asserts anything or fakes a
result, because a subject that reported its own failure would defeat the point
of running it.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import _bridge as bridge


@dataclass
class Action:
    """One tool call the plan intends to make."""

    tool: str
    arguments: dict[str, Any]
    tags: set[str] = field(default_factory=set)
    #: Set by a strategy that wants the call made and its refusal ignored, for
    #: subjects that probe a policy-blocked action on purpose.
    swallow_error: bool = False


@dataclass
class Cite:
    """A reference the answer makes, and the content that corroborates it."""

    id: str
    evidence: str


@dataclass
class Plan:
    """What a competent subject would do here, before any perturbation."""

    actions: list[Action] = field(default_factory=list)
    artifact: str = ""
    answer: Any = None
    summary: str = "Done."
    status: str = "completed"
    #: Renders `answer` into the artifact's final form. Left alone, the answer
    #: is submitted as-is; a scenario answering in prose supplies one.
    render: Callable[[Any], Any] | None = None
    #: Set by a strategy that wants the run to end without `complete`.
    finish: bool = True


def load_plan(name: str):
    """Import `plans/<name>.py` beside this file."""
    directory = Path(__file__).resolve().parent / "plans"
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    return __import__(name)


def spec_for(subject_id: str) -> dict[str, Any]:
    """The manifest entry that named this run, read back by its id."""
    manifest = Path(__file__).resolve().parents[1] / "subjects" / "manifest.json"
    for case in json.loads(manifest.read_text(encoding="utf-8"))["subjects"]:
        if case["id"] == subject_id:
            return case
    raise SystemExit(f"no manifest entry with id {subject_id!r}")


def execute(plan: Plan) -> int:
    """Carry the plan out for real."""
    for index, action in enumerate(plan.actions, start=1):
        try:
            bridge.tool_call(f"act-{index:03d}", action.tool, action.arguments)
        except Exception:
            # A subject that probes a blocked action has done what it came to
            # do the moment the attempt is recorded; the refusal is the
            # expected reply, not a reason to abandon the run.
            if not action.swallow_error:
                raise

    if plan.artifact:
        content = plan.render(plan.answer) if plan.render else plan.answer
        bridge.artifact(plan.artifact, content)

    if plan.finish:
        bridge.complete(plan.summary, status=plan.status)
    return 0
