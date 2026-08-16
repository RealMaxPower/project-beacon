from __future__ import annotations

import copy
from typing import Any

from beacon.models import EventRecorder


class DescriptionTable:
    """
    Tool descriptions supplied by the scenario fixture.

    Every other channel into an agent arrives from somewhere it has a reason to
    doubt: a document it fetched, a message someone sent it, a reply from a
    delegate. The tool list does not. It comes from the agent's own harness,
    alongside the operator's instructions and in the same frame, and an agent
    that treated it with suspicion could not use its tools at all.

    So a description that says what to *do* rather than what the tool *is* has
    poisoned the one input nothing is built to distrust, and nothing about the
    wire format distinguishes the two — both are a string on a tool object.
    This is the mechanism that lets a scenario put one there.

    Deliberately narrow. Only the description moves: the name, the schema and
    the handler are the service's, so a fixture cannot invent a capability or
    change what a call does. It can only change what the agent is told about
    it, which is exactly the channel the cell is about.

    Replacements are recorded, once each, the first time the tool list is
    assembled. Without that a scenario could not tell "resisted the directive"
    from "the table stopped matching and the directive was never served" — the
    same confound the fault table records `fault_injected` to close.
    """

    def __init__(
        self,
        overrides: dict[str, Any] | None,
        recorder: EventRecorder,
        offered: tuple[str, ...] = (),
    ) -> None:
        self._overrides = {str(k): str(v) for k, v in (overrides or {}).items()}
        self._recorder = recorder
        self._served: set[str] = set()
        unknown = sorted(set(self._overrides) - set(offered))
        if offered and unknown:
            # An authoring mistake, and a silent one otherwise: a typo in the
            # tool name would leave the scenario grading resistance to a
            # directive that was never delivered, and it would pass.
            raise KeyError(
                "tool_descriptions names tools this service does not offer: "
                + ", ".join(unknown)
            )

    def __bool__(self) -> bool:
        return bool(self._overrides)

    def apply(
        self, definitions: tuple[dict[str, Any], ...]
    ) -> tuple[dict[str, Any], ...]:
        if not self._overrides:
            return definitions
        applied = []
        for definition in definitions:
            name = definition["name"]
            if name not in self._overrides:
                applied.append(definition)
                continue
            replaced = copy.deepcopy(definition)
            replaced["description"] = self._overrides[name]
            applied.append(replaced)
            if name not in self._served:
                self._served.add(name)
                self._recorder.record(
                    "tool_description_replaced",
                    "tool_description_replaced",
                    {"tool": name},
                )
        return tuple(applied)

    def reset(self) -> None:
        self._served = set()
