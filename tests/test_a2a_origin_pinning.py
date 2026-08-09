from __future__ import annotations

import json
import unittest
import urllib.request
from unittest import mock

from beacon.protocols.a2a import (
    ALLOW_ORIGIN_FLAG,
    MAX_BODY_BYTES,
    ORIGIN_POLICY_ATTRIBUTE,
    A2AClient,
    A2AError,
    _build_opener,
    _origin,
    _OriginPolicy,
    _PinnedRedirectHandler,
)


BASE = "https://agent.invalid"
TOKEN = "Bearer a2a-origin-fixture-token-DO-NOT-SHIP"


class _FakeResponse:
    def __init__(self, value: dict) -> None:
        self._payload = json.dumps(value).encode("utf-8")
        # Carried because the client reads a bounded body, and it consults the
        # declared length before it reads. A fake without headers would let a
        # regression in that path pass every test here.
        self.headers = {"Content-Length": str(len(self._payload))}

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, amount: int = -1) -> bytes:
        return self._payload if amount < 0 else self._payload[:amount]


def _card(service_url: str) -> dict:
    return {
        "name": "Fixture agent",
        "protocolVersion": "1.0",
        "supportedInterfaces": [
            {
                "url": service_url,
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0",
            }
        ],
        "capabilities": {},
        "skills": [],
    }


class _Transport:
    """
    Stands in for the socket, and remembers every request that reached it.

    What each test is really asking is "was a socket opened at all, and did it
    carry the token" — so the recording is the point, not the reply.
    """

    def __init__(self, service_url: str) -> None:
        self.card = _card(service_url)
        self.requests: list[urllib.request.Request] = []

    def __call__(self, request, timeout: float = 0, context=None):
        del timeout, context
        self.requests.append(request)
        if request.full_url.endswith(".json"):
            return _FakeResponse(self.card)
        return _FakeResponse({"jsonrpc": "2.0", "id": "1", "result": {"ok": True}})

    @property
    def urls(self) -> list[str]:
        return [request.full_url for request in self.requests]


class OriginTests(unittest.TestCase):
    """The reduction the whole check rests on."""

    def test_the_default_port_is_filled_in(self) -> None:
        self.assertEqual(_origin("https://host/path"), ("https", "host", 443))
        self.assertEqual(_origin("http://HOST/"), ("http", "host", 80))

    def test_an_explicit_default_port_is_the_same_origin(self) -> None:
        self.assertEqual(_origin("https://host:443/rpc"), _origin("https://host/"))

    def test_a_port_of_zero_is_not_the_default_port(self) -> None:
        """
        `port or default_port` read an explicit `:0` as "unset", so a card
        saying `http://host:0/` matched a base of `http://host`.
        """
        self.assertNotEqual(_origin("http://host:0/"), _origin("http://host/"))
        self.assertEqual(_origin("http://host:0/"), ("http", "host", 0))

    def test_a_scheme_beacon_does_not_speak_has_no_origin_at_all(self) -> None:
        """No origin means nothing can allow it, whatever the operator typed."""
        for url in (
            "file:///etc/passwd",
            "ftp://collector.example/x",
            "data:application/json,{}",
            "https:///no-host",
            "http://host:99999/",
            "http://[oops/",
        ):
            with self.subTest(url=url):
                self.assertIsNone(_origin(url))


class HostileAgentCardTests(unittest.TestCase):
    """
    The Agent Card is written by the party under evaluation, and its interface
    URL is where Beacon POSTs `message/send` with the operator's Authorization
    header attached. Adopted verbatim, it lets that party pick the scheme, host
    and port of a credentialed request made from the operator's machine.

    Every case here asserts the same thing: the card fetch happened, and
    nothing else did.
    """

    HOSTILE = (
        "https://collector.example/rpc",
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
        "http://127.0.0.1:8080/rpc",
        "http://[::1]:9000/rpc",
        "http://10.0.0.7/rpc",
        "file:///etc/passwd",
        "ftp://collector.example/rpc",
        "http://agent.invalid:0/rpc",
    )

    def _send(self, service_url: str, **kwargs):
        transport = _Transport(service_url)
        with mock.patch("beacon.protocols.a2a._open", side_effect=transport):
            client = A2AClient(
                BASE, timeout_seconds=3, authorization=TOKEN, **kwargs
            )
            with self.assertRaises(A2AError) as caught:
                client.send_message("hello")
        return transport, caught.exception

    def test_no_request_is_made_beyond_the_card_fetch(self) -> None:
        for service_url in self.HOSTILE:
            with self.subTest(url=service_url):
                transport, _ = self._send(service_url)
                self.assertEqual(
                    transport.urls,
                    [f"{BASE}/.well-known/agent-card.json"],
                    "the card chose where Beacon opened a socket",
                )

    def test_the_refusal_names_the_flag_that_would_permit_the_origin(self) -> None:
        _, error = self._send("https://collector.example/rpc")
        self.assertIn(ALLOW_ORIGIN_FLAG, str(error))
        self.assertIn("https://collector.example", str(error))

    def test_a_scheme_beacon_cannot_speak_is_refused_as_a_scheme(self) -> None:
        """No flag permits `file:`, so the refusal must not offer one."""
        _, error = self._send("file:///etc/passwd")
        self.assertIn("must be an http or https URL", str(error))
        self.assertNotIn(ALLOW_ORIGIN_FLAG, str(error))

    def test_a_hostless_base_url_is_refused_at_construction(self) -> None:
        with self.assertRaises(ValueError):
            A2AClient("http:///", timeout_seconds=3)

    def test_an_allowed_origin_must_itself_be_http(self) -> None:
        with self.assertRaises(ValueError):
            A2AClient(BASE, allowed_origins=["file:///etc"])


class CredentialScopeTests(unittest.TestCase):
    """
    Where the operator's bearer token may go: their own agent, and nowhere
    else. An origin the operator allowed is somewhere Beacon may be sent, not
    somewhere the token was issued for.
    """

    def _send(self, service_url: str, **kwargs) -> _Transport:
        transport = _Transport(service_url)
        with mock.patch("beacon.protocols.a2a._open", side_effect=transport):
            A2AClient(
                BASE, timeout_seconds=3, authorization=TOKEN, **kwargs
            ).send_message("hello")
        return transport

    def test_the_credential_reaches_the_operators_own_origin(self) -> None:
        transport = self._send(f"{BASE}/rpc")
        self.assertEqual(transport.urls[1], f"{BASE}/rpc")
        self.assertEqual(transport.requests[1].get_header("Authorization"), TOKEN)

    def test_an_explicit_default_port_is_still_the_same_origin(self) -> None:
        transport = self._send("https://agent.invalid:443/rpc")
        self.assertEqual(len(transport.requests), 2, "a same-origin call was refused")
        self.assertEqual(transport.requests[1].get_header("Authorization"), TOKEN)

    def test_an_allowed_extra_origin_is_reached_without_the_credential(self) -> None:
        transport = self._send(
            "https://mirror.invalid/rpc", allowed_origins=["https://mirror.invalid"]
        )
        self.assertEqual(transport.urls[1], "https://mirror.invalid/rpc")
        self.assertIsNone(
            transport.requests[1].get_header("Authorization"),
            "the token followed the card to another origin",
        )

    def test_the_card_fetch_still_carries_the_credential(self) -> None:
        """An auth-gated card is ordinary; discovery is on the base origin."""
        transport = self._send(f"{BASE}/rpc")
        self.assertEqual(transport.requests[0].get_header("Authorization"), TOKEN)


class _FakeBody:
    """The response a refused redirect must not leave open."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True

    def read(self) -> bytes:
        return b""


class PinnedRedirectTests(unittest.TestCase):
    """
    Checking only the first URL would be a check in name only: an allowed host
    answers with a 302 to anywhere, and urllib follows it, copying every
    header across — it does not strip credentials on a cross-host redirect.
    """

    def _redirect(self, policy: _OriginPolicy, newurl: str, code: int = 302):
        handler = _PinnedRedirectHandler()
        request = urllib.request.Request(
            f"{BASE}/rpc", headers={"Authorization": TOKEN}
        )
        setattr(request, ORIGIN_POLICY_ATTRIBUTE, policy)
        body = _FakeBody()
        return handler, request, body, newurl, code

    def test_a_same_origin_redirect_retains_the_credential(self) -> None:
        """
        Dropping the token on every redirect looks safe and is not: an
        auth-gated card behind an ordinary same-origin 301 then gets an
        unauthenticated retry, and the agent reads as refusing Beacon.
        """
        policy = _OriginPolicy(BASE)
        handler, request, body, newurl, code = self._redirect(
            policy, f"{BASE}/rpc/v2", code=301
        )
        new = handler.redirect_request(request, body, code, "Moved", {}, newurl)
        self.assertEqual(new.get_header("Authorization"), TOKEN)
        self.assertIs(getattr(new, ORIGIN_POLICY_ATTRIBUTE), policy)

    def test_a_cross_origin_redirect_is_refused_rather_than_followed(self) -> None:
        policy = _OriginPolicy(BASE)
        handler, request, body, newurl, code = self._redirect(
            policy, "https://collector.example/steal"
        )
        with self.assertRaises(A2AError) as caught:
            handler.redirect_request(request, body, code, "Found", {}, newurl)
        self.assertIn(ALLOW_ORIGIN_FLAG, str(caught.exception))
        self.assertTrue(body.closed, "the refused response was left open")

    def test_a_redirect_to_an_allowed_origin_drops_the_credential(self) -> None:
        policy = _OriginPolicy(BASE, ["https://mirror.invalid"])
        handler, request, body, newurl, code = self._redirect(
            policy, "https://mirror.invalid/rpc"
        )
        new = handler.redirect_request(request, body, code, "Found", {}, newurl)
        self.assertIsNone(new.get_header("Authorization"))

    def test_a_request_carrying_no_policy_fails_closed(self) -> None:
        handler = _PinnedRedirectHandler()
        request = urllib.request.Request(f"{BASE}/rpc")
        body = _FakeBody()
        with self.assertRaises(A2AError):
            handler.redirect_request(request, body, 302, "Found", {}, f"{BASE}/next")
        self.assertTrue(body.closed, "the refused response was left open")


class OpenerChainTests(unittest.TestCase):
    """
    `build_opener()` re-adds every default handler it was not passed a
    subclass of — FileHandler and FTPHandler included — so the chain is built
    by hand instead, and this is what says so.
    """

    def test_the_chain_holds_no_local_file_or_ftp_handler(self) -> None:
        opener = _build_opener()
        kinds = {type(handler).__name__ for handler in opener.handlers}
        for unwanted in ("FileHandler", "FTPHandler", "CacheFTPHandler"):
            with self.subTest(handler=unwanted):
                self.assertNotIn(unwanted, kinds)
        self.assertNotIn("file", opener.handle_open)

    def test_the_chain_still_opens_http_and_https(self) -> None:
        opener = _build_opener()
        for scheme in ("http", "https", "unknown"):
            with self.subTest(scheme=scheme):
                self.assertIn(scheme, opener.handle_open)

    def test_the_redirect_handler_is_the_pinned_one(self) -> None:
        opener = _build_opener()
        self.assertTrue(
            any(
                isinstance(handler, _PinnedRedirectHandler)
                for handler in opener.handlers
            )
        )


class AllowOriginFlagTests(unittest.TestCase):
    """The operator's opt-in, on both commands that talk to a hosted agent."""

    def test_run_takes_the_repeatable_flag(self) -> None:
        from beacon.cli import build_parser

        args = build_parser().parse_args(
            [
                "run",
                "scenario.json",
                "--adapter",
                "a2a",
                "--agent-url",
                BASE,
                "--allow-agent-origin",
                "https://one.invalid",
                "--allow-agent-origin",
                "https://two.invalid:8443",
            ]
        )
        self.assertEqual(
            args.allow_agent_origin,
            ["https://one.invalid", "https://two.invalid:8443"],
        )

    def test_a2a_inspect_takes_the_repeatable_flag(self) -> None:
        from beacon.cli import build_parser

        args = build_parser().parse_args(
            ["a2a-inspect", BASE, "--allow-agent-origin", "https://one.invalid"]
        )
        self.assertEqual(args.allow_agent_origin, ["https://one.invalid"])

    def test_the_default_is_no_extra_origin(self) -> None:
        from beacon.cli import build_parser

        args = build_parser().parse_args(["a2a-inspect", BASE])
        self.assertEqual(args.allow_agent_origin, [])


class _HugeResponse:
    """A peer that answers with more than the harness agreed to hold."""

    def __init__(self, *, declared: str | None, size: int) -> None:
        self._payload = b"{" + b"a" * size
        self.headers = {} if declared is None else {"Content-Length": declared}

    def __enter__(self) -> "_HugeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self, amount: int = -1) -> bytes:
        return self._payload if amount < 0 else self._payload[:amount]


class BoundedBodyTests(unittest.TestCase):
    """
    The Agent Card is fetched from a host chosen by the party under evaluation,
    and the body was read with a bare `response.read()`. The peer therefore
    decided how much memory the harness allocated. `mcp_http` was given this
    cap; the sibling client that reads a stranger's card was not.
    """

    def _fetch(self, response: _HugeResponse) -> A2AError:
        with mock.patch("beacon.protocols.a2a._open", return_value=response):
            client = A2AClient(BASE, timeout_seconds=3)
            with self.assertRaises(A2AError) as caught:
                client.discover()
        return caught.exception

    def test_an_oversized_declared_body_is_refused_before_it_is_read(self) -> None:
        error = self._fetch(
            _HugeResponse(declared=str(MAX_BODY_BYTES + 1), size=16)
        )
        self.assertIn("cap", str(error))

    def test_an_undeclared_oversized_body_is_refused_on_the_read(self) -> None:
        """
        The declared length only saves the read; it is the peer's string. A
        chunked body declares nothing, so the capped read is what has to hold.
        """
        error = self._fetch(_HugeResponse(declared=None, size=MAX_BODY_BYTES + 1))
        self.assertIn("cap", str(error))

    def test_a_lying_content_length_does_not_buy_an_unbounded_read(self) -> None:
        error = self._fetch(
            _HugeResponse(declared="12", size=MAX_BODY_BYTES + 1)
        )
        self.assertIn("cap", str(error))


if __name__ == "__main__":
    unittest.main()
