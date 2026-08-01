from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from beacon.protocols import A2AClient, A2AError, MCPError, MCPStdioClient


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


class MCPStreamRobustnessTests(unittest.TestCase):
    """
    Found by running the client against seven third-party servers rather than
    only against this repo's own fixture: a blank line in the stream — which a
    real server emitted while its launcher was still installing — was treated
    as a protocol violation and failed the run.
    """

    NOISY_SERVER = (
        "import sys, json\n"
        "for raw in sys.stdin:\n"
        "    msg = json.loads(raw)\n"
        "    if msg.get('id') is None:\n"
        "        continue\n"
        "    sys.stdout.write('\\n')\n"          # blank line before the reply
        "    sys.stdout.write('   \\n')\n"        # and a whitespace-only one
        "    result = ({'protocolVersion': '2025-06-18', 'capabilities': {},\n"
        "               'serverInfo': {'name': 'noisy', 'version': '1'}}\n"
        "              if msg['method'] == 'initialize' else {'tools': []})\n"
        "    sys.stdout.write(json.dumps("
        "{'jsonrpc': '2.0', 'id': msg['id'], 'result': result}) + '\\n')\n"
        "    sys.stdout.flush()\n"
    )

    BROKEN_SERVER = (
        "import sys, json\n"
        "sys.stderr.write('launcher: could not resolve package\\n')\n"
        "sys.stderr.flush()\n"
        "for raw in sys.stdin:\n"
        "    sys.stdout.write('this is not json\\n')\n"
        "    sys.stdout.flush()\n"
    )

    def test_blank_lines_are_skipped_not_fatal(self) -> None:
        with MCPStdioClient(
            [sys.executable, "-c", self.NOISY_SERVER], timeout_seconds=10
        ) as client:
            self.assertEqual(client.server_info["name"], "noisy")
            self.assertEqual(client.list_tools(), [])

    def test_unparseable_output_reports_the_method_and_stderr(self) -> None:
        """The old message was 'invalid JSON: ' and named neither."""
        with self.assertRaises(MCPError) as caught:
            MCPStdioClient(
                [sys.executable, "-c", self.BROKEN_SERVER], timeout_seconds=10
            ).start()
        message = str(caught.exception)
        self.assertIn("initialize", message)
        self.assertIn("this is not json", message)
        self.assertIn("could not resolve package", message)


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


class StartupCleanupTests(unittest.TestCase):
    """
    A `start()` that raises must not leave the child running.

    The caller never receives the client, so it has nothing to close, and the
    process and its three pipes survive until the interpreter collects them —
    reported as "subprocess N is still running" and three unclosed files.

    The documented test command is `-W error::ResourceWarning`, which cannot
    fail on any of this: the warnings surface from `__del__` and from reader
    threads, where they print as "Exception ignored" and the suite stays green.
    So the leak is asserted directly rather than left to a flag that cannot see
    it.
    """

    def test_a_failed_handshake_reaps_the_child(self) -> None:
        client = MCPStdioClient(
            [sys.executable, "-c", MCPStreamRobustnessTests.BROKEN_SERVER],
            timeout_seconds=10,
        )
        with self.assertRaises(MCPError):
            client.start()
        self.assertIsNone(
            client._process, "the client still holds a process it never closed"
        )

    def test_a_server_that_never_answers_is_not_left_running(self) -> None:
        silent = "import sys, time\ntime.sleep(30)\n"
        client = MCPStdioClient([sys.executable, "-c", silent], timeout_seconds=1)
        with self.assertRaises(MCPError):
            client.start()
        self.assertIsNone(client._process)

    def test_a_healthy_client_still_starts_and_closes(self) -> None:
        """The cleanup must not fire on the path that works."""
        client = MCPStdioClient(
            [sys.executable, "-c", MCPStreamRobustnessTests.NOISY_SERVER], timeout_seconds=10
        )
        client.start()
        self.assertIsNotNone(client._process)
        client.close()
        self.assertIsNone(client._process)
