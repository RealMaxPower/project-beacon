from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from beacon.protocols import MCPError, MCPHTTPClient
from beacon.protocols.mcp_http import _parse_sse


def _rpc_result(request_id: Any, method: str) -> dict[str, Any]:
    if method == "initialize":
        return {
            "protocolVersion": "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "fixture", "version": "1"},
        }
    return {"tools": [{"name": "do_thing", "description": "d", "inputSchema": {}}]}


class _Server:
    """A configurable MCP-ish server, for the shapes real ones actually send."""

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.paths: list[str] = []
        handler = self._handler()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}/mcp"

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def _handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_: Any) -> None:
                pass

            def do_POST(self) -> None:  # noqa: N802
                outer.paths.append(self.path)
                length = int(self.headers.get("Content-Length", "0"))
                message = json.loads(self.rfile.read(length) or b"{}")

                if outer.mode == "redirect" and self.path == "/mcp":
                    self.send_response(308)
                    self.send_header("Location", "/mcp/v2")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return

                if message.get("id") is None:
                    self.send_response(202)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return

                payload = {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "result": _rpc_result(message["id"], message["method"]),
                }
                if outer.mode == "sse":
                    body = f"event: message\ndata: {json.dumps(payload)}\n\n".encode()
                    content_type = "text/event-stream"
                elif outer.mode == "html":
                    body = b"<!DOCTYPE html><html>nope</html>"
                    content_type = "text/html; charset=utf-8"
                else:
                    body = json.dumps(payload).encode()
                    content_type = "application/json"

                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Mcp-Session-Id", "sess-1")
                self.end_headers()
                self.wfile.write(body)

        return Handler


class SSEParsingTests(unittest.TestCase):
    def test_a_single_event_is_extracted(self) -> None:
        body = 'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{}}\n\n'
        self.assertEqual(_parse_sse(body)[0]["id"], 1)

    def test_data_split_across_lines_is_rejoined(self) -> None:
        body = 'data: {"jsonrpc":"2.0",\ndata: "id":2,"result":{}}\n\n'
        self.assertEqual(_parse_sse(body)[0]["id"], 2)

    def test_a_trailing_event_without_a_blank_line_is_kept(self) -> None:
        self.assertEqual(len(_parse_sse('data: {"id":3}')), 1)

    def test_non_event_noise_is_ignored(self) -> None:
        body = ': keep-alive\nevent: ping\n\ndata: {"id":4}\n\n'
        self.assertEqual([m["id"] for m in _parse_sse(body)], [4])


class TransportTests(unittest.TestCase):
    """
    Streamable HTTP lets the *server* choose JSON or SSE, so a client that
    understands only one silently fails against everything that picks the
    other. Both are exercised here against a real socket.
    """

    def _client(self, mode: str) -> MCPHTTPClient:
        server = _Server(mode)
        self.addCleanup(server.stop)
        self.server = server
        return MCPHTTPClient(server.url, timeout_seconds=10)

    def test_a_json_server_completes_the_handshake(self) -> None:
        client = self._client("json")
        client.start()
        self.assertEqual(client.server_info["name"], "fixture")
        self.assertEqual([t["name"] for t in client.list_tools()], ["do_thing"])

    def test_an_sse_server_completes_the_handshake(self) -> None:
        client = self._client("sse")
        client.start()
        self.assertEqual(client.server_info["name"], "fixture")
        self.assertEqual([t["name"] for t in client.list_tools()], ["do_thing"])

    def test_the_session_id_is_echoed_back(self) -> None:
        client = self._client("json")
        client.start()
        self.assertEqual(client.session_id, "sess-1")

    def test_a_permanent_redirect_is_followed_with_the_body_intact(self) -> None:
        """
        Found in the wild: urllib refuses to follow 307/308 for POST, so a
        server that redirects to a canonical path looked unreachable.
        """
        client = self._client("redirect")
        client.start()
        self.assertTrue(client.url.endswith("/mcp/v2"))
        self.assertIn("/mcp/v2", self.server.paths)

    def test_an_html_error_page_names_the_content_type(self) -> None:
        client = self._client("html")
        with self.assertRaises(MCPError) as caught:
            client.start()
        self.assertIn("text/html", str(caught.exception))

    def test_a_non_http_url_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            MCPHTTPClient("ftp://example.invalid/mcp")


if __name__ == "__main__":
    unittest.main()
