#!/usr/bin/env python3
"""
Drive Beacon's MCP façade with the *official* MCP SDK, not Beacon's own client.

    pip install mcp
    python3 -m beacon run scenarios/inbox-briefing/scenario.json \
      --adapter mcp-host \
      --command "python3 conformance/official_sdk_client.py"

Beacon's façade had only ever been talked to by the reference host in
`examples/`, which this repo also wrote — so it proved that Beacon agrees with
Beacon. This host uses the reference implementation of the protocol instead.
If the façade deviates from the spec in a way the hand-written client happened
to tolerate, this is what catches it.

Requires the `mcp` package. Beacon's core still has no runtime dependencies;
this lives in `conformance/` precisely because it needs one.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any


async def run() -> int:
    try:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client
    except ImportError:
        print("the official mcp SDK is not installed: pip install mcp", file=sys.stderr)
        return 2

    url = os.environ.get("BEACON_MCP_URL")
    token = os.environ.get("BEACON_MCP_TOKEN")
    if not url or not token:
        print("BEACON_MCP_URL and BEACON_MCP_TOKEN are required", file=sys.stderr)
        return 2

    headers = {"Authorization": f"Bearer {token}"}
    async with streamablehttp_client(url, headers=headers, timeout=60) as (
        read_stream,
        write_stream,
        _get_session_id,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            init = await session.initialize()
            print(
                f"[sdk] initialized against {init.serverInfo.name} "
                f"{init.serverInfo.version} (protocol {init.protocolVersion})",
                file=sys.stderr,
            )

            listing = await session.list_tools()
            available = {tool.name for tool in listing.tools}
            print(f"[sdk] tools: {sorted(available)}", file=sys.stderr)

            async def call(name: str, arguments: dict[str, Any]) -> Any:
                result = await session.call_tool(name, arguments)
                if result.isError:
                    text = " ".join(
                        getattr(block, "text", "") for block in result.content
                    )
                    raise RuntimeError(f"{name} failed: {text}")
                if result.structuredContent is not None:
                    return result.structuredContent.get("result")
                return " ".join(getattr(b, "text", "") for b in result.content)

            handled: list[dict[str, Any]] = []
            if "mail_list_messages" in available:
                headers_ = await call("mail_list_messages", {})
                for header in headers_:
                    if "action_required" not in header.get("labels", []):
                        continue
                    if header.get("protected"):
                        continue
                    message = await call(
                        "mail_read_message", {"message_id": header["id"]}
                    )
                    handled.append(message)
                    if "mail_create_draft" in available:
                        await call(
                            "mail_create_draft",
                            {
                                "to": message["sender"],
                                "subject": f"Re: {message['subject']}",
                                "body": (
                                    "Thanks for the note. I reviewed it and will "
                                    "confirm the requested next step after a "
                                    "human review."
                                ),
                                "in_reply_to": message["id"],
                            },
                        )

            briefing = "Action-required inbox briefing\n\n" + "\n".join(
                f"- [{m['id']}] {m['subject']} — {m['body']}" for m in handled
            )
            if "beacon_submit" in available:
                await call(
                    "beacon_submit",
                    {
                        "status": "completed",
                        "summary": f"Prepared {len(handled)} draft responses.",
                        "artifact": briefing,
                    },
                )
            print("[sdk] submitted", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
