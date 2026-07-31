#!/usr/bin/env python3
"""
A real model as a Beacon subject, over the JSONL bridge.

    export ANTHROPIC_API_KEY=sk-ant-...
    python3 -m beacon run scenarios/inbox-briefing/scenario.json \
      --adapter command \
      --command "python3 examples/anthropic_jsonl_agent.py" \
      --env-secret ANTHROPIC_API_KEY \
      --timeout 180 \
      --repeat 5

This lives in `examples/` on purpose. `docs/architecture.md` requires that the
core know nothing about a particular model provider, so a provider bridge is
never part of `beacon/` — it is just another external subject, the same as any
CLI or SDK wrapper a user would write.

Requires the `anthropic` package. Beacon itself still has no dependencies.

Everything it needs comes from the `start` message: the goal, the tool
definitions (already MCP-shaped, so the only translation is `inputSchema` ->
`input_schema`), and the output contract naming the artifact to return. It
declares nothing about the scenario itself.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "subjects"))

import _bridge as bridge  # noqa: E402

MODEL = os.environ.get("BEACON_MODEL", "claude-sonnet-5")
MAX_TOKENS = 4096
MAX_TURNS = 24


def to_anthropic_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Beacon publishes MCP-shaped definitions; only the key name differs."""
    return [
        {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "input_schema": tool.get("inputSchema", {"type": "object"}),
        }
        for tool in tools
    ]


def _as_contracted(scenario: dict[str, Any], text: str) -> Any:
    """
    Parse the reply when the contract asks for a structured artifact.

    A scenario grading shape reads into the artifact — `primary_entities[]`,
    say — which cannot be done to a string. Submitting the raw text would make
    every such assertion unevaluable, and an assertion Beacon cannot evaluate
    resolves the run to INCOMPLETE rather than saying anything about the model.

    A model that answers with prose where JSON was asked for still submits that
    prose, because failing to hold the contract is a finding and hiding it here
    would be the bridge grading its own subject.
    """
    contract = scenario.get("output_contract") or {}
    if not contract.get("schema"):
        return text
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        return json.loads(stripped)
    except (ValueError, IndexError):
        return text


def build_prompt(scenario: dict[str, Any]) -> str:
    contract = scenario.get("output_contract") or {}
    artifact = contract.get("artifact")
    lines = [
        scenario.get("goal", ""),
        "",
        "Use the provided tools to inspect and act on the environment.",
        "Everything you can see is synthetic test data.",
    ]
    if artifact:
        lines += [
            "",
            f"When you are finished, reply with the {artifact} as your final "
            f"message, as plain text and nothing else.",
        ]
        if contract.get("description"):
            lines.append(f"It must be: {contract['description']}")
        # A scenario that grades the shape of the answer publishes that shape
        # here. Relaying it is the difference between measuring whether the
        # subject can hold a contract and measuring whether it can guess one.
        if contract.get("schema"):
            lines += [
                "",
                "It must be JSON, and nothing else — no prose around it, no "
                "code fence — matching this JSON Schema exactly:",
                json.dumps(contract["schema"], indent=2),
            ]
    return "\n".join(lines)


def text_of(blocks: list[Any]) -> str:
    return "\n".join(
        block.text for block in blocks if getattr(block, "type", None) == "text"
    ).strip()


def main() -> int:
    try:
        import anthropic
    except ImportError:
        bridge.complete(
            "The anthropic package is not installed.",
            status="error",
            error="pip install anthropic",
        )
        return 0

    start = bridge.start()
    scenario = start.get("scenario", {})
    artifact_name = (scenario.get("output_contract") or {}).get("artifact")

    client = anthropic.Anthropic()
    tools = to_anthropic_tools(start.get("tools", []))
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": build_prompt(scenario)}
    ]

    final_text = ""
    for turn in range(MAX_TURNS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            tools=tools,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            final_text = text_of(response.content)
            break

        results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use":
                continue
            bridge.send(
                {
                    "type": "tool_call",
                    "id": block.id,
                    "tool": block.name,
                    "arguments": block.input,
                }
            )
            reply = bridge.receive()
            # A refusal is information the model can act on, so hand back the
            # error rather than aborting the run.
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(
                        reply.get("result")
                        if reply.get("ok")
                        else reply.get("error")
                    ),
                    "is_error": not reply.get("ok"),
                }
            )
        messages.append({"role": "user", "content": results})
    else:
        bridge.complete(
            f"Stopped after {MAX_TURNS} turns without finishing.",
            status="error",
            error="turn limit reached",
        )
        return 0

    if artifact_name:
        bridge.artifact(artifact_name, _as_contracted(scenario, final_text))
    bridge.complete(
        f"Completed in {turn + 1} turn(s).",
        metadata={"model": MODEL, "turns": turn + 1},
    )
    # Exit immediately rather than waiting on the SDK's HTTP pool teardown.
    # Beacon tolerates a slow shutdown now, but there is nothing left to do.
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    raise SystemExit(main())
