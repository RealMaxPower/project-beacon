from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

from beacon.protocols import A2AClient, MCPStdioClient


ROOT = Path(__file__).resolve().parents[1]
MCP_FIXTURE = ROOT / "examples" / "mcp_echo_server.py"


class MCPTests(unittest.TestCase):
    def test_stdio_discovery_and_tool_call(self) -> None:
        with MCPStdioClient(
            [sys.executable, str(MCP_FIXTURE)],
            timeout_seconds=5,
        ) as client:
            tools = client.list_tools()
            self.assertEqual(tools[0]["name"], "echo")
            result = client.call_tool("echo", {"text": "hello"})
            self.assertEqual(result["structuredContent"], {"text": "hello"})
            self.assertEqual(client.server_info["name"], "beacon-echo-fixture")


class _FakeResponse:
    def __init__(self, value: dict) -> None:
        self._payload = json.dumps(value).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


class A2ATests(unittest.TestCase):
    def test_discovery_and_message(self) -> None:
        base_url = "https://fixture.invalid"

        def fake_urlopen(request: object, timeout: float) -> _FakeResponse:
            del timeout
            url = request.full_url
            if url.endswith("/.well-known/agent-card.json"):
                return _FakeResponse(
                    {
                        "name": "Beacon A2A fixture",
                        "description": "An in-memory test agent",
                        "supportedInterfaces": [
                            {
                                "url": base_url,
                                "protocolBinding": "HTTP+JSON",
                                "protocolVersion": "1.0",
                            }
                        ],
                        "capabilities": {"streaming": False},
                        "skills": [],
                    }
                )
            self.assertTrue(url.endswith("/message:send"))
            message = json.loads(request.data)["message"]
            return _FakeResponse(
                {
                    "task": {
                        "id": "task-fixture",
                        "status": {"state": "TASK_STATE_COMPLETED"},
                        "artifacts": [
                            {
                                "name": "echo",
                                "parts": [{"text": message["parts"][0]["text"]}],
                            }
                        ],
                    }
                }
            )

        with mock.patch(
            "beacon.protocols.a2a.urllib.request.urlopen",
            side_effect=fake_urlopen,
        ):
            client = A2AClient(base_url, timeout_seconds=3)
            card = client.discover()
            self.assertEqual(card["name"], "Beacon A2A fixture")
            response = client.send_message("hello")
            artifact = response["task"]["artifacts"][0]
            self.assertEqual(artifact["parts"][0]["text"], "hello")


if __name__ == "__main__":
    unittest.main()
