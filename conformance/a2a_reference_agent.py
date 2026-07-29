#!/usr/bin/env python3
"""
An A2A agent built with the official SDK, to check Beacon's client against.

    pip install "a2a-sdk[http-server]" fastapi uvicorn
    python3 conformance/a2a_reference_agent.py 8731          # 1.0 only
    python3 conformance/a2a_reference_agent.py 8732 --v03    # + 0.3 methods

Then, from another shell:

    python3 -m beacon a2a-inspect http://127.0.0.1:8731 --send hello
    python3 -m beacon run hosted-injection-resistance \
      --adapter a2a --agent-url http://127.0.0.1:8731

Why this exists. Beacon's A2A client was written from the specification and
then repaired against four live agents, all of which speak 0.x. Its 1.x path
had never met a 1.x server. Pointing it at the reference implementation found
three defects in an afternoon, the worst of which reported a working agent as
INCOMPLETE — "did not run" — because it answered with a Message instead of a
Task, which `message/send` explicitly permits and which this SDK does by
default for any agent with no long-running work to track.

The SDK is a heavy dependency and this needs a live port, so it is not part of
the unit suite. The wire shapes it produced are pinned in
`tests/test_a2a_response_shapes.py`, which runs everywhere with no SDK at all.
Re-run this against a new SDK release to find out whether those shapes still
hold.
"""

from __future__ import annotations

import sys
import uuid

try:
    import uvicorn
    from fastapi import FastAPI
    from a2a.server.agent_execution import AgentExecutor, RequestContext
    from a2a.server.events import EventQueue
    from a2a.server.request_handlers import DefaultRequestHandler
    from a2a.server.routes import (
        add_a2a_routes_to_fastapi,
        create_agent_card_routes,
        create_jsonrpc_routes,
    )
    from a2a.server.tasks import InMemoryTaskStore
    from a2a.types import (
        AgentCapabilities,
        AgentCard,
        AgentInterface,
        AgentSkill,
        Message,
        Part,
        Role,
    )
except ImportError as error:  # pragma: no cover - depends on optional extras
    sys.exit(
        f"{error}\n\nInstall the reference server's dependencies first:\n"
        '    pip install "a2a-sdk[http-server]" fastapi uvicorn'
    )


PORT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8731
COMPAT_0_3 = "--v03" in sys.argv


class EchoExecutor(AgentExecutor):
    """
    Echoes what it was sent, and nothing else.

    Deliberately trivial. The point is to exercise the transport, the card
    shape and the reply shape — not to be a good agent. An echo makes it
    obvious in the evidence whether Beacon received the reply at all.
    """

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        text = context.get_user_input() or ""
        await event_queue.enqueue_event(
            Message(
                message_id=str(uuid.uuid4()),
                role=Role.ROLE_AGENT,
                parts=[Part(text=f"REFERENCE-AGENT-SAW: {text[:200]}")],
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("the reference agent has nothing to cancel")


def build_card(port: int) -> AgentCard:
    """
    A 1.x card, which has no top-level `url`.

    Endpoints live in `supportedInterfaces`, each carrying its own binding and
    protocol version. A client that reads only the 0.x `url` field sees a card
    that declares no interface at all.
    """
    return AgentCard(
        name="Beacon reference A2A agent",
        description="Official-SDK agent used to check Beacon's A2A client.",
        version="1.0.0",
        supported_interfaces=[
            AgentInterface(
                url=f"http://127.0.0.1:{port}/",
                protocol_binding="JSONRPC",
                protocol_version="1.0",
            )
        ],
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["text"],
        default_output_modes=["text"],
        skills=[
            AgentSkill(
                id="echo", name="echo", description="Echoes its input.", tags=["test"]
            )
        ],
    )


def build_app(port: int, *, compat_0_3: bool) -> "FastAPI":
    card = build_card(port)
    handler = DefaultRequestHandler(
        agent_executor=EchoExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    app = FastAPI()
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(agent_card=card),
        jsonrpc_routes=create_jsonrpc_routes(
            request_handler=handler, rpc_url="/", enable_v0_3_compat=compat_0_3
        ),
    )
    return app


if __name__ == "__main__":
    mode = "1.0 + 0.3 compatibility" if COMPAT_0_3 else "1.0 only"
    print(f"Reference A2A agent on http://127.0.0.1:{PORT} ({mode})")
    print(f"Card: http://127.0.0.1:{PORT}/.well-known/agent-card.json")
    uvicorn.run(build_app(PORT, compat_0_3=COMPAT_0_3), host="127.0.0.1", port=PORT, log_level="error")
