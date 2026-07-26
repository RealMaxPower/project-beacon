from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from beacon.protocols import A2AClient, A2AError, MCPStdioClient


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


class A2AProtocolVersionTests(unittest.TestCase):
    """
    Deployed A2A agents speak 0.x. Beacon spoke only 1.x, so every live agent
    answered "method not found" — and the interface fallback compounded it by
    sending a REST POST to a JSON-RPC endpoint.
    """

    CARD_0X = {
        "name": "Fixture 0.x agent",
        "protocolVersion": "0.3.0",
        "url": "https://fixture.invalid/a2a/jsonrpc",
        "preferredTransport": "JSONRPC",
        "additionalInterfaces": [
            {"transport": "JSONRPC", "url": "https://fixture.invalid/a2a/jsonrpc"}
        ],
        "capabilities": {"streaming": True},
        "skills": [],
    }

    def _client(self, card: dict) -> tuple[A2AClient, list[dict]]:
        sent: list[dict] = []

        def fake_urlopen(request: object, timeout: float = 0, context=None):
            del timeout, context
            if request.full_url.endswith("/.well-known/agent-card.json"):
                return _FakeResponse(card)
            sent.append(json.loads(request.data))
            return _FakeResponse({"jsonrpc": "2.0", "id": "1", "result": {"ok": True}})

        patcher = mock.patch(
            "beacon.protocols.a2a.urllib.request.urlopen", side_effect=fake_urlopen
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return A2AClient("https://fixture.invalid", timeout_seconds=3), sent

    def test_a_0x_card_gets_the_0x_method_and_message_shape(self) -> None:
        client, sent = self._client(self.CARD_0X)
        client.discover()
        client.send_message("hello")
        body = sent[0]
        self.assertEqual(body["method"], "message/send")
        message = body["params"]["message"]
        self.assertEqual(message["role"], "user")
        self.assertEqual(message["parts"][0]["kind"], "text")

    def test_a_0x_card_routes_to_its_jsonrpc_endpoint(self) -> None:
        client, _ = self._client(self.CARD_0X)
        client.discover()
        interface = client._interface()
        self.assertEqual(interface["transport"], "JSONRPC")
        self.assertTrue(interface["url"].endswith("/a2a/jsonrpc"))

    def test_a_1x_card_keeps_the_1x_method_and_message_shape(self) -> None:
        card = {
            "name": "Fixture 1.x agent",
            "protocolVersion": "1.0",
            "supportedInterfaces": [
                {
                    "url": "https://fixture.invalid/rpc",
                    "protocolBinding": "JSONRPC",
                    "protocolVersion": "1.0",
                }
            ],
        }
        client, sent = self._client(card)
        client.discover()
        client.send_message("hello")
        body = sent[0]
        self.assertEqual(body["method"], "SendMessage")
        self.assertEqual(body["params"]["message"]["role"], "ROLE_USER")

    def test_a_jsonrpc_error_is_raised_not_returned_as_a_result(self) -> None:
        """A live agent's "method not found" must not read as a successful call."""

        def fake_urlopen(request: object, timeout: float = 0, context=None):
            del timeout, context
            if request.full_url.endswith("/.well-known/agent-card.json"):
                return _FakeResponse(self.CARD_0X)
            return _FakeResponse(
                {
                    "jsonrpc": "2.0",
                    "id": "1",
                    "error": {"code": -32601, "message": "Method not found"},
                }
            )

        with mock.patch(
            "beacon.protocols.a2a.urllib.request.urlopen", side_effect=fake_urlopen
        ):
            client = A2AClient("https://fixture.invalid", timeout_seconds=3)
            client.discover()
            with self.assertRaises(A2AError) as caught:
                client.send_message("hello")
        self.assertIn("Method not found", str(caught.exception))

    def test_requests_identify_themselves(self) -> None:
        """A WAF answers the default Python user agent with 403."""
        captured: list[Any] = []

        def fake_urlopen(request: object, timeout: float = 0, context=None):
            del timeout, context
            captured.append(request)
            return _FakeResponse(self.CARD_0X)

        with mock.patch(
            "beacon.protocols.a2a.urllib.request.urlopen", side_effect=fake_urlopen
        ):
            A2AClient("https://fixture.invalid").discover()
        self.assertIn("project-beacon", captured[0].get_header("User-agent", ""))


class A2ATests(unittest.TestCase):
    def test_discovery_and_message(self) -> None:
        base_url = "https://fixture.invalid"

        def fake_urlopen(
            request: object, timeout: float = 0, context: object = None
        ) -> _FakeResponse:
            del timeout, context
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
