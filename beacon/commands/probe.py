from __future__ import annotations

"""The commands that inspect someone else's server: `mcp-inspect`, `a2a-inspect`."""

import argparse
import json

from beacon.cliargs import split_command
from beacon.protocols import A2AClient, MCPStdioClient


def mcp_inspect(args: argparse.Namespace) -> int:
    command = split_command(args.command)
    with MCPStdioClient(command, timeout_seconds=args.timeout) as client:
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
