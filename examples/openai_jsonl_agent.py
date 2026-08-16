#!/usr/bin/env python3
"""
Any OpenAI-compatible endpoint as a Beacon subject, over the JSONL bridge.

    export OPENAI_API_KEY=sk-...
    python3 -m beacon run inbox-briefing \
      --adapter command \
      --command "python3 examples/openai_jsonl_agent.py --model gpt-4o" \
      --env-secret OPENAI_API_KEY \
      --timeout 180 \
      --repeat 5

`/v1/chat/completions` with tool calling is the one shape almost every provider
and every local server agrees on, so `--base-url` is most of what this file is
for:

    --base-url https://api.groq.com/openai/v1     --model llama-3.3-70b-versatile
    --base-url https://openrouter.ai/api/v1       --model anthropic/claude-sonnet-4
    --base-url http://localhost:11434/v1          --model qwen2.5     # Ollama
    --base-url http://localhost:1234/v1           --model local-model # LM Studio
    --base-url http://localhost:8000/v1           --model ...         # vLLM

**No dependencies.** `urllib` only, so this runs in the same empty environment
Beacon itself runs in — a bridge that needed a package to install would be a
worse answer than the SDK bridge beside it, not a better one. A local server
usually needs no key at all, and none is sent when the variable is unset.

Like `anthropic_jsonl_agent.py`, this lives in `examples/` because
`docs/architecture.md` requires the core to know nothing about a particular
provider. It is an external subject, exactly like a CLI wrapper you would
write.

**What a verdict from this measures.** A model, in Beacon's scaffold, on this
prompt. It is not a measurement of *your* agent: the loop here is forty lines
and yours is not, and a failure may belong to either. Grade your own agent by
pointing this bridge's `--command` slot at it instead.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "subjects"))

import _bridge as bridge  # noqa: E402

MAX_TURNS = 24
REQUEST_TIMEOUT = 120


def to_openai_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Beacon publishes MCP-shaped definitions; the wrapper is the difference.

    `inputSchema` becomes `parameters`, and a tool with no schema still needs
    one — several servers reject a function whose `parameters` is absent, and
    an empty object is what "takes no arguments" looks like here.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema") or {
                    "type": "object",
                    "properties": {},
                },
            },
        }
        for tool in tools
    ]


def _as_contracted(scenario: dict[str, Any], text: str) -> Any:
    """
    Parse the reply when the contract asks for a structured artifact.

    A scenario grading shape reads into the artifact, which cannot be done to a
    string, so submitting raw text would make every such assertion unevaluable
    — and an unevaluable assertion resolves the run to INCOMPLETE rather than
    saying anything about the model.

    A model that answers with prose where JSON was asked for still submits that
    prose. Failing to hold the contract is a finding, and repairing it here
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
        # subject can hold a contract and whether it can guess one.
        if contract.get("schema"):
            lines += [
                "",
                "It must be JSON, and nothing else — no prose around it, no "
                "code fence — matching this JSON Schema exactly:",
                json.dumps(contract["schema"], indent=2),
            ]
    return "\n".join(lines)


def chat(url: str, key: str | None, payload: dict[str, Any]) -> dict[str, Any]:
    """
    One `/chat/completions` call.

    The key is read from the environment and never from an argument, so it
    cannot reach a process listing or a shell history — the same rule
    `docs/running-it-yourself.md` states for every other subject.
    """
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def _arguments(call: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    """
    The arguments of one tool call, which arrive as a JSON *string*.

    A model that emits malformed JSON here is making a real mistake, and the
    honest thing is to hand the parse error back as the tool's reply rather
    than to crash the bridge — a crashed subject is INCOMPLETE, which says
    nothing, while a returned error is something the model can correct.
    """
    raw = (call.get("function") or {}).get("arguments") or "{}"
    if isinstance(raw, dict):
        return raw, ""
    try:
        parsed = json.loads(raw)
    except ValueError as exc:
        return None, f"arguments were not valid JSON: {exc}"
    if not isinstance(parsed, dict):
        return None, f"arguments must be a JSON object, got {type(parsed).__name__}"
    return parsed, ""


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get(
        "OPENAI_BASE_URL", "https://api.openai.com/v1"))
    parser.add_argument("--model", default=os.environ.get("BEACON_MODEL", "gpt-4o"))
    parser.add_argument(
        "--api-key-env",
        default="OPENAI_API_KEY",
        help="Environment variable holding the key. The key itself is never "
             "an argument. Unset is allowed: local servers take no key.",
    )
    parser.add_argument("--max-turns", type=int, default=MAX_TURNS)
    arguments = parser.parse_args(argv)

    url = arguments.base_url.rstrip("/") + "/chat/completions"
    key = os.environ.get(arguments.api_key_env) or None

    start = bridge.start()
    scenario = start.get("scenario", {})
    artifact_name = (scenario.get("output_contract") or {}).get("artifact")

    tools = to_openai_tools(start.get("tools", []))
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": build_prompt(scenario)}
    ]

    final_text = ""
    # Accumulated across turns, not read off the last one. A tool-using run is
    # several billed requests, and the final response knows only about itself.
    spend = {"prompt_tokens": 0, "completion_tokens": 0}
    turn = 0
    for turn in range(arguments.max_turns):
        payload: dict[str, Any] = {"model": arguments.model, "messages": messages}
        if tools:
            payload["tools"] = tools
        try:
            response = chat(url, key, payload)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:500]
            bridge.complete(
                f"The endpoint returned HTTP {exc.code}.",
                status="error",
                error=f"HTTP {exc.code}: {detail}",
                metadata={"model": arguments.model, "base_url": arguments.base_url},
            )
            return 0
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            bridge.complete(
                "The endpoint could not be reached.",
                status="error",
                error=f"{type(exc).__name__}: {exc}",
                metadata={"model": arguments.model, "base_url": arguments.base_url},
            )
            return 0

        usage = response.get("usage") or {}
        for name in spend:
            spend[name] += int(usage.get(name) or 0)

        choice = (response.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        calls = message.get("tool_calls") or []

        if not calls:
            final_text = (message.get("content") or "").strip()
            break

        # Echoed back verbatim: the next request has to carry the assistant
        # turn that made the calls, or the tool replies below refer to nothing.
        messages.append(
            {
                "role": "assistant",
                "content": message.get("content"),
                "tool_calls": calls,
            }
        )

        for index, call in enumerate(calls):
            # Servers that omit the id are common enough to matter; a reply
            # with no `tool_call_id` is rejected by the ones that do not.
            call_id = call.get("id") or f"call-{turn}-{index}"
            name = (call.get("function") or {}).get("name", "")
            parsed, problem = _arguments(call)
            if parsed is None:
                content, ok = problem, False
            else:
                bridge.send(
                    {
                        "type": "tool_call",
                        "id": call_id,
                        "tool": name,
                        "arguments": parsed,
                    }
                )
                reply = bridge.receive()
                ok = bool(reply.get("ok"))
                # A refusal is information the model can act on, so hand back
                # the error rather than aborting the run.
                content = str(reply.get("result") if ok else reply.get("error"))
            messages.append(
                {"role": "tool", "tool_call_id": call_id, "content": content}
            )
    else:
        bridge.complete(
            f"Stopped after {arguments.max_turns} turns without finishing.",
            status="error",
            error="turn limit reached",
            metadata={
                "model": arguments.model,
                "turns": arguments.max_turns,
                "usage": spend,
            },
        )
        # Reported on the failing path too. A run that hit the turn limit is
        # the expensive one, and dropping the figure exactly when it is largest
        # would make it useless for the case it is wanted for.
        return 0

    if artifact_name:
        bridge.artifact(artifact_name, _as_contracted(scenario, final_text))
    bridge.complete(
        f"Completed in {turn + 1} turn(s).",
        metadata={"model": arguments.model, "turns": turn + 1, "usage": spend},
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
