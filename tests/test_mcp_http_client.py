from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from beacon.protocols import MCPError, MCPHTTPClient
from beacon.protocols import mcp_server
from beacon.protocols.mcp_http import (
    MAX_BODY_BYTES,
    MAX_REDIRECTS,
    _is_internal,
    _parse_sse,
    _refuse_internal,
)


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

    def __init__(
        self,
        mode: str,
        *,
        location: str = "/mcp",
        declared: str | None = None,
    ) -> None:
        self.mode = mode
        self.location = location
        self.declared = declared
        self.paths: list[str] = []
        self.seen: list[dict[str, str | None]] = []
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
                outer.seen.append(
                    {
                        "authorization": self.headers.get("Authorization"),
                        "session": self.headers.get("Mcp-Session-Id"),
                    }
                )
                length = int(self.headers.get("Content-Length", "0"))
                message = json.loads(self.rfile.read(length) or b"{}")

                if outer.mode == "redirect" and self.path == "/mcp":
                    self.send_response(308)
                    self.send_header("Location", "/mcp/v2")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return

                if outer.mode == "redirect-to":
                    self.send_response(308)
                    self.send_header("Location", outer.location)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return

                if outer.mode == "soft-redirect-to":
                    # 301/302/303 are urllib's to follow, not ours; it turns
                    # the POST into a GET and copies the headers across.
                    self.send_response(302)
                    self.send_header("Location", outer.location)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return

                if outer.mode == "over-declared":
                    # Claims more than the cap and then sends nothing: a client
                    # that trusts the header allocates before a byte arrives.
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(MAX_BODY_BYTES + 1))
                    self.send_header("Connection", "close")
                    self.end_headers()
                    return

                if outer.mode == "over-undeclared":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.wfile.write(b"x" * (MAX_BODY_BYTES + 1))
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
                elif outer.mode == "at-cap":
                    payload["result"]["pad"] = ""
                    payload["result"]["pad"] = "x" * (
                        MAX_BODY_BYTES - len(json.dumps(payload).encode())
                    )
                    body = json.dumps(payload).encode()
                    content_type = "application/json"
                else:
                    body = json.dumps(payload).encode()
                    content_type = "application/json"

                self.send_response(200)
                self.send_header("Content-Type", content_type)
                if outer.declared is None:
                    self.send_header("Content-Length", str(len(body)))
                else:
                    # A length no one can parse, so the body ends at the close.
                    self.send_header("Content-Length", outer.declared)
                    self.send_header("Connection", "close")
                self.send_header("Mcp-Session-Id", "sess-1")
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802
                # Where a 301/302/303 lands, so the headers it carried can be
                # inspected.
                outer.paths.append(self.path)
                outer.seen.append(
                    {
                        "authorization": self.headers.get("Authorization"),
                        "session": self.headers.get("Mcp-Session-Id"),
                    }
                )
                body = json.dumps(
                    {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
                ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
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


class RedirectSafetyTests(unittest.TestCase):
    """
    Endpoint URLs come from a public registry, so a 307/308 `Location` is
    written by whoever registered the server. Following one by hand is what
    makes that worth testing: the target decides the scheme, the host, and
    therefore who receives the caller's bearer token.
    """

    def _client(self, server: _Server, **kwargs: Any) -> MCPHTTPClient:
        self.addCleanup(server.stop)
        return MCPHTTPClient(server.url, timeout_seconds=10, **kwargs)

    def _canary(self) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        canary = Path(tmp.name) / "canary.txt"
        canary.write_text("BEACON-CANARY-SECRET", encoding="utf-8")
        return canary

    def test_a_redirect_to_another_scheme_is_refused(self) -> None:
        canary = self._canary()
        server = _Server("redirect-to", location=canary.as_uri())
        client = self._client(server)
        with self.assertRaises(MCPError) as caught:
            client.start()
        message = str(caught.exception)
        self.assertIn("refusing redirect", message)
        self.assertNotIn("BEACON-CANARY-SECRET", message)
        self.assertEqual(client.url, server.url)

    def test_the_opener_cannot_open_a_file_url(self) -> None:
        """Belt to the redirect check's braces: the opener has no file handler."""
        canary = self._canary()
        server = _Server("json")
        client = self._client(server)
        client.url = canary.as_uri()
        with self.assertRaises(MCPError) as caught:
            client._post({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        message = str(caught.exception)
        self.assertIn("could not reach", message)
        self.assertNotIn("BEACON-CANARY-SECRET", message)

    def test_a_same_origin_redirect_still_carries_the_credentials(self) -> None:
        server = _Server("redirect")
        client = self._client(server, authorization="Bearer secret-token")
        client.session_id = "sess-0"
        client.start()
        self.assertEqual(client.authorization, "Bearer secret-token")
        followed = server.seen[1]
        self.assertEqual(followed["authorization"], "Bearer secret-token")
        self.assertEqual(followed["session"], "sess-0")

    def test_a_cross_origin_redirect_drops_the_credentials(self) -> None:
        target = _Server("json")
        self.addCleanup(target.stop)
        source = _Server("redirect-to", location=target.url)
        client = self._client(source, authorization="Bearer secret-token")
        client.session_id = "sess-0"
        client.start()
        self.assertIsNone(client.authorization)
        self.assertIsNone(target.seen[0]["authorization"])
        self.assertIsNone(target.seen[0]["session"])

    def test_a_redirect_loop_stops_at_the_limit(self) -> None:
        server = _Server("redirect-to", location="/mcp")
        client = self._client(server)
        with self.assertRaises(MCPError) as caught:
            client.start()
        self.assertIn("HTTP 308", str(caught.exception))
        self.assertEqual(len(server.paths), MAX_REDIRECTS + 1)


class ResponseSizeTests(unittest.TestCase):
    """
    The peer decides how many bytes come back, and the sweep runs six of these
    at once, so the read is capped at the same size the server side accepts.
    """

    def _client(self, mode: str, **server_kwargs: Any) -> MCPHTTPClient:
        server = _Server(mode, **server_kwargs)
        self.addCleanup(server.stop)
        return MCPHTTPClient(server.url, timeout_seconds=10)

    def test_the_cap_matches_the_one_the_server_enforces(self) -> None:
        self.assertEqual(MAX_BODY_BYTES, mcp_server.MAX_BODY_BYTES)

    def test_an_over_cap_declared_length_is_refused(self) -> None:
        client = self._client("over-declared")
        with self.assertRaises(MCPError) as caught:
            client.start()
        self.assertIn("cap", str(caught.exception))

    def test_an_over_cap_undeclared_body_is_refused(self) -> None:
        client = self._client("over-undeclared")
        with self.assertRaises(MCPError) as caught:
            client.start()
        self.assertIn("cap", str(caught.exception))

    def test_a_body_exactly_at_the_cap_is_still_parsed(self) -> None:
        client = self._client("at-cap")
        client.start()
        self.assertEqual(client.server_info["name"], "fixture")

    def test_a_content_length_that_is_not_ascii_digits_is_ignored(self) -> None:
        """`'²'.isdigit()` is True and `int('²')` raises: not a crash here."""
        client = self._client("json", declared="²")
        client.start()
        self.assertEqual(client.server_info["name"], "fixture")

    def test_an_absurdly_long_content_length_is_ignored(self) -> None:
        """`int()` refuses a string past 4300 digits, which http.client survives."""
        client = self._client("json", declared="1" * 4301)
        client.start()
        self.assertEqual(client.server_info["name"], "fixture")


class SoftRedirectTests(unittest.TestCase):
    """
    307 and 308 are followed by hand; 301, 302 and 303 are followed by urllib
    itself, which copies every header to wherever it is sent. Checking only the
    hops we follow ourselves would be a check in name only — the server just
    answers 302 instead.
    """

    def _pair(self, location_path: str) -> tuple[_Server, _Server]:
        landing = _Server("json")
        self.addCleanup(landing.stop)
        location = (
            landing.url.rsplit("/mcp", 1)[0] + location_path
            if location_path.startswith("/")
            else location_path
        )
        origin = _Server("soft-redirect-to", location=location)
        self.addCleanup(origin.stop)
        return origin, landing

    def test_a_cross_origin_302_does_not_forward_the_credentials(self) -> None:
        landing = _Server("json")
        self.addCleanup(landing.stop)
        origin = _Server("soft-redirect-to", location=landing.url)
        self.addCleanup(origin.stop)

        client = MCPHTTPClient(
            origin.url, timeout_seconds=10, authorization="Bearer secret"
        )
        client.session_id = "sess-0"
        try:
            client._post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        except MCPError:
            pass

        self.assertTrue(landing.seen, "the redirect never landed")
        for record in landing.seen:
            self.assertIsNone(record["authorization"])
            self.assertIsNone(record["session"])

    def test_a_same_origin_302_keeps_the_credentials(self) -> None:
        """An auth-gated server behind its own 301 must not get logged out."""
        origin, _ = self._pair("/moved")
        client = MCPHTTPClient(
            origin.url, timeout_seconds=10, authorization="Bearer secret"
        )
        client.session_id = "sess-0"
        origin.location = origin.url.rsplit("/mcp", 1)[0] + "/moved"
        try:
            client._post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        except MCPError:
            pass

        self.assertGreaterEqual(len(origin.seen), 2, "the redirect was not followed")
        self.assertEqual(origin.seen[-1]["authorization"], "Bearer secret")
        self.assertEqual(origin.seen[-1]["session"], "sess-0")


class InternalAddressTests(unittest.TestCase):
    """
    Endpoint URLs come from a public registry, so a redirect is the registrant
    choosing where the harness sends its next request. Pointing it inward is
    refused — unless the operator aimed it inward to begin with, which is how
    a server on localhost gets tested.
    """

    def test_link_local_and_private_addresses_are_internal(self) -> None:
        for host in ("169.254.169.254", "127.0.0.1", "10.0.0.5"):
            with self.subTest(host=host):
                self.assertTrue(_is_internal(host))

    def test_a_name_that_does_not_resolve_is_not_called_internal(self) -> None:
        """A DNS failure is a DNS failure, not a security error."""
        self.assertFalse(_is_internal("no-such-host.invalid"))

    def test_a_public_origin_may_not_redirect_inward(self) -> None:
        public = ("https", "agent.example", 443)
        for host in ("169.254.169.254", "127.0.0.1"):
            with self.subTest(host=host):
                self.assertTrue(_refuse_internal(public, ("http", host, 80)))

    def test_a_local_origin_may_still_redirect_locally(self) -> None:
        self.assertFalse(
            _refuse_internal(("http", "127.0.0.1", 9000), ("http", "127.0.0.1", 9001))
        )

    def test_a_same_origin_hop_is_never_refused(self) -> None:
        public = ("https", "agent.example", 443)
        self.assertFalse(_refuse_internal(public, public))


if __name__ == "__main__":
    unittest.main()
