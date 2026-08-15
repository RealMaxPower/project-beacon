"""
The perturbations, as pure functions over a plan.

Each takes the plan a competent subject would carry out and returns the plan a
particular kind of incompetent one would. Nothing here executes anything or
knows what assertion it is expected to break — a strategy that checked its own
work would be reporting a result rather than producing one, and the whole value
of the adversarial suite is that the failures are observed rather than
declared.

Adding a strategy is the cheap half of adding a scenario. The expensive half is
the plan module, which is written once per scenario and is where the actual
domain knowledge lives.
"""

from __future__ import annotations

import copy
from typing import Any, Callable

from _plan import Action, Plan


def control(plan: Plan) -> Plan:
    """The competent baseline, unchanged. Every scenario needs one."""
    return plan


def forbidden_action(plan: Plan, *, tool: str, arguments: dict[str, Any]) -> Plan:
    """Append a call to a tool the scenario offers and the goal forbids."""
    plan.actions.append(Action(tool, arguments, swallow_error=True))
    return plan


def exfiltrate(plan: Plan, *, read: str, field: str = "themes",
               tool: str = "files_read", argument: str = "path",
               take: str = "content") -> Plan:
    """
    Obey an instruction to disclose something the goal withheld.

    The one strategy that reads from the world rather than only rearranging the
    plan, and it has to: the content it leaks does not exist until something
    fetches it, and splicing a hard-coded copy of the confidential text into
    this file would mean the canary lived in the subject rather than in the
    fixture — which is the same mistake as putting it in the payload.

    The read happens here, during the transform, so the leaked value is
    available to place in the answer before anything is submitted. `tool`,
    `argument` and `take` name the call because the confidential thing is a
    document in one service and a page in another, and the failure is the same
    failure either way.
    """
    import _bridge as bridge

    document = bridge.tool_call("exfil-001", tool, {argument: read})
    leaked = " ".join(str(document.get(take, "")).split())
    if isinstance(plan.answer, list):
        plan.answer = [*plan.answer, leaked]
    elif isinstance(plan.answer, dict) and isinstance(plan.answer.get(field), list):
        plan.answer[field] = [*plan.answer[field], leaked]
    elif isinstance(plan.answer, dict):
        plan.answer[field] = leaked
    else:
        plan.answer = f"{plan.answer}\n{leaked}"
    return plan


def repeat_action(plan: Plan, *, tag: str, times: int = 3) -> Plan:
    """Do a whole family of actions again, for count ceilings."""
    extra = [a for a in plan.actions if tag in a.tags]
    for _ in range(times - 1):
        plan.actions.extend(copy.deepcopy(extra))
    return plan


def drop_actions(plan: Plan, *, tag: str, keep: int = 0) -> Plan:
    """Stop doing a family of actions partway, for count floors."""
    kept, dropped = [], 0
    for action in plan.actions:
        if tag in action.tags:
            dropped += 1
            if dropped > keep:
                continue
        kept.append(action)
    plan.actions = kept
    return plan


def drop_answers(plan: Plan, *, keep: int = 1) -> Plan:
    """
    Truncate the answer itself, for the floors that count what came back.

    Distinct from `drop_actions`, which stops the subject *doing* things. This
    one lets it do all the work and then report a fraction of it — the shape of
    an agent that gets bored, or that summarises a long list by dropping most
    of it.
    """
    if isinstance(plan.answer, list):
        plan.answer = plan.answer[:keep]
    elif isinstance(plan.answer, dict):
        for field, value in plan.answer.items():
            if isinstance(value, list):
                plan.answer[field] = value[:keep]
    return plan


def drop_citations(plan: Plan) -> Plan:
    """
    Keep every reference, drop what corroborates it.

    The name-drop: an answer that lists the identifiers without having read
    what they point at. `cites` exists to reject exactly this, and this is what
    proves it still does.
    """
    for cite in _cites(plan):
        cite.evidence = ""
    return plan


def fabricate(plan: Plan, *, claims: list[str], field: str | None = None) -> Plan:
    """
    Add content to the answer that appears in no source.

    `field` names the list to fabricate into, and matters more than it looks.
    A grounding assertion reads one path — `artifacts.ledger.figures` — so an
    invented value dropped into a new key beside it changes the answer without
    changing anything the scenario grades, and the breaker passes. That is a
    subject which fabricated and was scored as honest, which is the failure
    this whole family is about.
    """
    if field is not None:
        if not isinstance(plan.answer, dict) or not isinstance(
            plan.answer.get(field), list
        ):
            raise SystemExit(f"fabricate: no list at answer[{field!r}]")
        plan.answer[field] = [*plan.answer[field], *claims]
        return plan
    for index, claim in enumerate(claims):
        plan.answer = _append_to_answer(plan.answer, claim, index)
    return plan


def mangle_shape(plan: Plan, *, edits: list[dict[str, Any]]) -> Plan:
    """Rename, remove or retype fields of a structured answer."""
    if not isinstance(plan.answer, dict):
        raise SystemExit("mangle_shape needs a structured answer")
    for edit in edits:
        operation, field = edit["op"], edit["path"]
        if operation == "remove":
            plan.answer.pop(field, None)
        elif operation == "rename":
            plan.answer[edit["to"]] = plan.answer.pop(field, None)
        elif operation == "set":
            plan.answer[field] = edit["to"]
        else:
            raise SystemExit(f"unknown mangle_shape op: {operation}")
    return plan


def ignore_format(plan: Plan, *, text: str) -> Plan:
    """Answer in prose where a shape was asked for."""
    plan.answer = text
    plan.render = None
    return plan


def wrong_artifact_name(plan: Plan, *, name: str) -> Plan:
    """Submit under a name the contract does not ask for."""
    plan.artifact = name
    return plan


def never_complete(plan: Plan) -> Plan:
    """Do everything, then never say so."""
    plan.finish = False
    return plan


def finish_anyway(plan: Plan, *, tool: str = "", arguments: dict[str, Any] | None = None,
                  summary: str = "Done.") -> Plan:
    """
    Push through an obstacle the goal said to stop at.

    The inverse of `escalate`, and the breaker the deferral family needs. An
    agent that guesses between two equally good candidates, or reconciles
    against the wrong month because the right one was missing, produces a
    confident artifact built on a decision nobody authorised — and the decision
    is invisible in the output, which is what makes it worse than stopping.
    """
    plan.status = "completed"
    plan.summary = summary
    if tool:
        plan.actions.append(Action(tool, arguments or {}, swallow_error=True))
    return plan


def escalate(plan: Plan, *, question: str) -> Plan:
    """Do the work, then stop to ask a question nothing required."""
    plan.status = "input_required"
    plan.summary = question
    return plan


STRATEGIES: dict[str, Callable[..., Plan]] = {
    "control": control,
    "exfiltrate": exfiltrate,
    "forbidden_action": forbidden_action,
    "repeat_action": repeat_action,
    "drop_actions": drop_actions,
    "drop_answers": drop_answers,
    "drop_citations": drop_citations,
    "fabricate": fabricate,
    "mangle_shape": mangle_shape,
    "ignore_format": ignore_format,
    "wrong_artifact_name": wrong_artifact_name,
    "never_complete": never_complete,
    "escalate": escalate,
    "finish_anyway": finish_anyway,
}


def _cites(plan: Plan) -> list[Any]:
    return plan.answer if isinstance(plan.answer, list) else []


def _append_to_answer(answer: Any, claim: str, index: int) -> Any:
    if isinstance(answer, str):
        return f"{answer}\n{claim}"
    if isinstance(answer, list):
        from _plan import Cite

        return [*answer, Cite(id=f"invented-{index}", evidence=claim)]
    if isinstance(answer, dict):
        return {**answer, f"invented_{index}": claim}
    return answer
