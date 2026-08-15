#!/usr/bin/env python3
"""
One subject, driven by a manifest entry.

Reads the scenario's competent baseline from `plans/`, applies the one
perturbation the manifest asks for, and carries the result out for real. That
is the whole of it — the interesting code is in the plan module, which is
written once per scenario, and in `_strategies.py`, which is written once for
everybody.

What this replaces: a Python file per adversarial subject. At seven scenarios
that was forty-seven files, which was tolerable. At the ~55 scenarios the
taxonomy asks for it would be two or three hundred, each one a near-copy of a
neighbour, and the suite would be shaped by what was cheap to write rather than
by what needed measuring.

Invoked as `breaker.py <manifest-subject-id>`. The id is enough: the manifest
entry it names carries the plan, the strategy and its parameters.
"""

from __future__ import annotations

import sys

import _bridge as bridge
import _plan
import _strategies


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        raise SystemExit("usage: breaker.py <manifest-subject-id>")
    spec = _plan.spec_for(argv[0])

    # Consume the start message before anything else reads from stdin, or the
    # plan's first tool call collects it as that call's response.
    bridge.start()

    strategy_name = spec.get("strategy", "control")
    strategy = _strategies.STRATEGIES.get(strategy_name)
    if strategy is None:
        raise SystemExit(f"unknown strategy: {strategy_name}")

    module = _plan.load_plan(spec["plan"])
    # The baseline's discovery runs here, against the real services, before any
    # perturbation exists. A strategy transforms what a competent subject
    # decided to do; it does not get to decide what the world looks like.
    #
    # `plan_params` is for the cases where the perturbation is inside the
    # discovery rather than after it — an agent that overspends a read budget
    # has already made the extra calls by the time there is a plan to
    # transform, so the baseline has to be told to behave that way rather than
    # be edited afterwards.
    plan = module.plan(**spec.get("plan_params", {}))

    return _plan.execute(strategy(plan, **spec.get("params", {})))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
