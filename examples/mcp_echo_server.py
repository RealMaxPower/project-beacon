#!/usr/bin/env python3
"""Tiny dependency-free MCP stdio fixture used by the Beacon test suite."""

from __future__ import annotations

import json
import sys


def respond(request: dict) -> None:
    method = request.get("method")
    request_id = request.get("id")
    if request_id is None:
        return
    if method == "initialize":
        result = {
            "protocolVersion": request.get("params", {}).get(
                "protocolVersion",
                "2025-06-18",
            ),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "beacon-echo-fixture", "version": "0.1.0"},
        }
    elif method == "tools/list":
        result = {
            "tools": [
                {
                    "name": "echo",
                    "description": "Return the provided text.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                    },
                }
            ]
        }
    elif method == "tools/call":
        params = request.get("params", {})
        if params.get("name") != "echo":
            payload = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": "unknown tool"},
            }
            print(json.dumps(payload), flush=True)
            return
        text = str(params.get("arguments", {}).get("text", ""))
        result = {
            "content": [{"type": "text", "text": text}],
            "structuredContent": {"text": text},
            "isError": False,
        }
    else:
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32601, "message": "method not found"},
        }
        print(json.dumps(payload), flush=True)
        return
    print(
        json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}),
        flush=True,
    )


for raw_line in sys.stdin:
    try:
        message = json.loads(raw_line)
    except json.JSONDecodeError:
        continue
    respond(message)

