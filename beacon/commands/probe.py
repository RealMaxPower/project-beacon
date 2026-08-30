from __future__ import annotations

"""The commands that inspect someone else's server: `mcp-inspect`, `a2a-inspect`."""

import argparse
import json

from beacon.cliargs import split_command
from beacon.protocols import A2AClient, MCPHTTPClient, MCPStdioClient


def mcp_inspect(args: argparse.Namespace) -> int:
    # `is not None` rather than truthiness: `--url ""` is falsy, and reading it
    # as "no URL given" sent an empty string down the stdio branch, where
    # `args.command` is None and `shlex.split(None)` is what answers. The
    # mutually-exclusive group guarantees one of the two was passed; it does not
    # guarantee the value is useful, and the branch has to be chosen on which
    # flag was given rather than on what it was given.
    if args.url is not None:
        client_context = MCPHTTPClient(
            args.url,
            timeout_seconds=args.timeout,
            authorization=args.authorization,
        )
    else:
        client_context = MCPStdioClient(
            split_command(args.command), timeout_seconds=args.timeout
        )
    with client_context as client:
        tools = client.list_tools()
        output = {
            "protocol_version": client.protocol_version,
            "server_info": client.server_info,
            "capabilities": client.capabilities,
            "tools": tools,
        }
        if args.call:
            output["call"] = {
                "tool": args.call,
                "arguments": args.arguments,
                "result": client.call_tool(args.call, args.arguments),
            }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0


def a2a_inspect(args: argparse.Namespace) -> int:
    client = A2AClient(
        args.url,
        timeout_seconds=args.timeout,
        authorization=args.authorization,
        allowed_origins=args.allow_agent_origin,
    )
    output = {"agent_card": client.discover()}
    if args.send:
        output["response"] = client.send_message(args.send)
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0
