from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from beacon.adapters import A2ASubjectAdapter
from beacon.models import Scenario
from beacon.runner import run_scenario


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios" / "hosted-injection-resistance" / "scenario.json"


CARD_1X = {
    "name": "Reference 1.x agent",
    "description": "Shaped exactly as the official a2a-sdk 1.1.2 serves it.",
    "version": "1.0.0",
    "supportedInterfaces": [
        {
            "url": "http://fixture.invalid/",
            "protocolBinding": "JSONRPC",
            "protocolVersion": "1.0",
        }
    ],
    "capabilities": {"streaming": False},
    "defaultInputModes": ["text"],
    "defaultOutputModes": ["text"],
    "skills": [{"id": "echo", "name": "echo", "description": "d", "tags": []}],
}

# Verbatim from the reference server. Note `ROLE_AGENT`: 1.x generates its
# wire format from protobuf, where the enum member name is what lands in JSON.
MESSAGE_REPLY = {
    "message": {
        "messageId": "1acf3d6b-005a-49eb-9894-a2a6aa2c6b28",
        "role": "ROLE_AGENT",
        "parts": [{"text": "Project Atlas enters phase two in October."}],
    }
}

TASK_REPLY = {
    "id": "task-1",
    "status": {"state": "completed"},
    "artifacts": [
        {"name": "report", "parts": [{"text": "Project Atlas, phase two."}]}
    ],
}


class _FakeResponse:
    def __init__(self, value: dict) -> None:
        self._payload = json.dumps(value).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


class MessageShapedReplyTests(unittest.TestCase):
    """
    `message/send` may answer with a Task or with a bare Message. Beacon
    handled only the Task, so an agent that simply replied was reported
    INCOMPLETE with no artifacts — and INCOMPLETE means "did not run", so the
    evidence stated the opposite of what happened.

    Found by running Beacon against a server built with the official a2a-sdk,
    which returns a Message for any agent with no long-running work to track.
    That is the default shape for the simplest kind of agent, not an edge case.
    """

    def _run(self, card: dict, result: dict):
        def fake_urlopen(request: object, timeout: float = 0, context=None):
            del timeout, context
            if request.full_url.endswith("/.well-known/agent-card.json"):
                return _FakeResponse(card)
            return _FakeResponse({"jsonrpc": "2.0", "id": "1", "result": result})

        patcher = mock.patch(
            "beacon.protocols.a2a._open", side_effect=fake_urlopen
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        with tempfile.TemporaryDirectory() as directory:
            return run_scenario(
                Scenario.load(SCENARIO),
                A2ASubjectAdapter("http://fixture.invalid", timeout_seconds=5),
                output_dir=directory,
                run_id="shape",
            ).evidence

    def test_a_message_reply_counts_as_a_completed_run(self) -> None:
        evidence = self._run(CARD_1X, MESSAGE_REPLY)
        self.assertNotEqual(evidence.result, "INCOMPLETE")
        completed = next(
            item for item in evidence.assertions if item["id"] == "task-completed"
        )
        self.assertTrue(completed["passed"])

    def test_the_message_text_is_stored_as_an_artifact(self) -> None:
        evidence = self._run(CARD_1X, MESSAGE_REPLY)
        self.assertTrue(evidence.artifacts, "the reply was dropped entirely")
        self.assertIn(
            "Atlas", json.dumps(evidence.artifacts), "the text never reached evidence"
        )

    def test_a_result_that_is_itself_the_message_is_understood(self) -> None:
        """Some servers do not wrap the message in a `message` key."""
        evidence = self._run(
            CARD_1X,
            {
                "messageId": "m-1",
                "role": "ROLE_AGENT",
                "parts": [{"text": "Project Atlas, phase two."}],
            },
        )
        self.assertIn("Atlas", json.dumps(evidence.artifacts))

    def test_the_protobuf_role_spelling_is_accepted(self) -> None:
        """
        0.x sends `agent`; 1.x sends `ROLE_AGENT`. Matching one spelling drops
        every reply from half the ecosystem — and the reference server sends
        `ROLE_AGENT` even in its 0.3 compatibility mode.
        """
        lowercase = {
            "message": {
                "messageId": "m-1",
                "role": "agent",
                "parts": [{"text": "Project Atlas, phase two."}],
            }
        }
        for reply in (MESSAGE_REPLY, lowercase):
            with self.subTest(role=reply["message"]["role"]):
                self.assertIn("Atlas", json.dumps(self._run(CARD_1X, reply).artifacts))

    def test_a_user_role_reply_is_not_mistaken_for_the_answer(self) -> None:
        """An echoed prompt is not the agent's answer."""
        evidence = self._run(
            CARD_1X,
            {
                "message": {
                    "messageId": "m-1",
                    "role": "ROLE_USER",
                    "parts": [{"text": "Project Atlas, phase two."}],
                }
            },
        )
        self.assertEqual(evidence.artifacts, {})

    def test_a_task_reply_still_works(self) -> None:
        """The path that already worked, pinned so the fix cannot break it."""
        evidence = self._run(CARD_1X, TASK_REPLY)
        self.assertIn("report", evidence.artifacts)
        completed = next(
            item for item in evidence.assertions if item["id"] == "task-completed"
        )
        self.assertTrue(completed["passed"])

    def test_a_task_with_an_unknown_state_is_still_incomplete(self) -> None:
        """
        The fix must not promote every statusless reply to success. A task
        that carries artifacts but no recognisable state is genuinely unknown,
        and calling it completed would be the pass-by-default this project
        exists to avoid.
        """
        evidence = self._run(
            CARD_1X,
            {"id": "task-1", "status": {"state": "weird"}, "artifacts": []},
        )
        self.assertEqual(evidence.result, "INCOMPLETE")

    def test_an_empty_result_is_not_promoted_to_completed(self) -> None:
        evidence = self._run(CARD_1X, {})
        self.assertEqual(evidence.result, "INCOMPLETE")


class OneDotXCardTests(unittest.TestCase):
    """
    The 1.x AgentCard has no top-level `url`: endpoints live in
    `supportedInterfaces`, each with its own binding and protocol version.
    """

    def _post_target(self, card: dict) -> str:
        from beacon.protocols.a2a import A2AClient

        sent: list[str] = []

        def fake_urlopen(request: object, timeout: float = 0, context=None):
            del timeout, context
            if request.full_url.endswith("/.well-known/agent-card.json"):
                return _FakeResponse(card)
            sent.append(request.full_url)
            return _FakeResponse({"jsonrpc": "2.0", "id": "1", "result": MESSAGE_REPLY})

        with mock.patch(
            "beacon.protocols.a2a._open", side_effect=fake_urlopen
        ):
            A2AClient("http://fixture.invalid", timeout_seconds=5).send_message("hi")
        return sent[0]

    def test_the_endpoint_is_found_inside_supported_interfaces(self) -> None:
        # Trailing slashes are normalised away before the request is built, so
        # compare without one rather than pinning a cosmetic detail.
        self.assertEqual(
            self._post_target(CARD_1X).rstrip("/"), "http://fixture.invalid"
        )

    def test_a_declared_path_is_used_rather_than_the_base_url(self) -> None:
        """
        The bug this guards against already happened once in the other
        direction: reading only the 1.x field made a 0.x card look empty, and
        the client posted to an endpoint the agent had never heard of.
        """
        card = dict(CARD_1X)
        card["supportedInterfaces"] = [
            {
                "url": "http://fixture.invalid/a2a/v1/rpc",
                "protocolBinding": "JSONRPC",
                "protocolVersion": "1.0",
            }
        ]
        self.assertEqual(
            self._post_target(card), "http://fixture.invalid/a2a/v1/rpc"
        )


class TransportDefaultTests(unittest.TestCase):
    """
    A 0.x card may omit `preferredTransport`. The specification declares
    `@default "JSONRPC"`; Beacon defaulted to the REST binding, so a card
    that left the field out got `POST /message:send` — a shape a JSON-RPC
    agent has never heard of.

    Found on agent.ai, whose live card is 0.3.0 with a top-level `url` and no
    transport field at all. It is the same failure that made every deployed
    agent unreachable before, arrived at from a different direction.
    """

    CARD_NO_TRANSPORT = {
        "name": "Agent.ai",
        "protocolVersion": "0.3.0",
        "url": "https://fixture.invalid",
        "capabilities": {},
        "skills": [],
    }

    def _send(self, card: dict) -> tuple[str, str | None]:
        from beacon.protocols.a2a import A2AClient

        sent: list[tuple[str, str | None]] = []

        def fake_urlopen(request: object, timeout: float = 0, context=None):
            del timeout, context
            if request.full_url.endswith(".json"):
                return _FakeResponse(card)
            body = json.loads(request.data)
            sent.append((request.full_url, body.get("method")))
            return _FakeResponse({"jsonrpc": "2.0", "id": "1", "result": {}})

        with mock.patch(
            "beacon.protocols.a2a._open", side_effect=fake_urlopen
        ):
            A2AClient("https://fixture.invalid", timeout_seconds=3).send_message("x")
        return sent[0]

    def test_an_omitted_transport_means_jsonrpc(self) -> None:
        url, method = self._send(self.CARD_NO_TRANSPORT)
        self.assertEqual(method, "message/send")
        self.assertFalse(url.endswith("/message:send"), "sent the REST shape")

    def test_an_empty_transport_string_is_treated_as_omitted(self) -> None:
        card = dict(self.CARD_NO_TRANSPORT, preferredTransport="")
        self.assertEqual(self._send(card)[1], "message/send")

    def test_an_explicit_rest_transport_is_still_honoured(self) -> None:
        """The default must not become an override."""
        card = dict(self.CARD_NO_TRANSPORT, preferredTransport="HTTP+JSON")
        url, method = self._send(card)
        self.assertTrue(url.endswith("/message:send"))
        self.assertIsNone(method)

    def test_an_explicit_jsonrpc_transport_still_works(self) -> None:
        card = dict(self.CARD_NO_TRANSPORT, preferredTransport="JSONRPC")
        self.assertEqual(self._send(card)[1], "message/send")


class VersionNegotiationTests(unittest.TestCase):
    """
    The `A2A-Version` header and the JSON-RPC method name have to describe the
    same protocol. The method name was chosen from the card while the header
    was a fixed "1.0", so every 0.3 agent received a request whose header
    claimed 1.0 and whose body called `message/send`.

    Every agent tested tolerated it by ignoring the header. The JavaScript SDK
    reads it, and answers the mismatched pair with an internal error — which
    Beacon would have recorded as the agent failing, on a request Beacon
    malformed.
    """

    def _sent(self, card_version: str) -> tuple[str | None, str]:
        from beacon.protocols.a2a import A2AClient

        card = {
            "name": "fixture",
            "protocolVersion": card_version,
            "url": "https://fixture.invalid",
            "preferredTransport": "JSONRPC",
            "capabilities": {},
            "skills": [],
        }
        seen: dict[str, Any] = {}

        def fake_urlopen(request: object, timeout: float = 0, context=None):
            del timeout, context
            if request.full_url.endswith(".json"):
                return _FakeResponse(card)
            seen["header"] = request.get_header("A2a-version")
            seen["method"] = json.loads(request.data)["method"]
            return _FakeResponse({"jsonrpc": "2.0", "id": "1", "result": {}})

        with mock.patch(
            "beacon.protocols.a2a._open", side_effect=fake_urlopen
        ):
            A2AClient("https://fixture.invalid", timeout_seconds=3).send_message("x")
        return seen["header"], seen["method"]

    def test_a_0x_card_negotiates_a_0x_header(self) -> None:
        header, method = self._sent("0.3.0")
        self.assertEqual(header, "0.3")
        self.assertEqual(method, "message/send")

    def test_a_1x_card_negotiates_a_1x_header(self) -> None:
        header, method = self._sent("1.0")
        self.assertEqual(header, "1.0")
        self.assertEqual(method, "SendMessage")

    def test_the_header_and_the_method_never_disagree(self) -> None:
        """The property that matters, stated once for every version seen live."""
        for version in ("0.2.5", "0.3", "0.3.0", "1.0", "1.1.0"):
            with self.subTest(version=version):
                header, method = self._sent(version)
                self.assertEqual(
                    header.startswith("0."),
                    method == "message/send",
                    f"header {header} disagrees with method {method}",
                )

    def _sent_for_card(self, card: dict) -> tuple[str | None, str]:
        from beacon.protocols.a2a import A2AClient

        seen: dict[str, Any] = {}

        def fake_urlopen(request: object, timeout: float = 0, context=None):
            del timeout, context
            if request.full_url.endswith(".json"):
                return _FakeResponse(card)
            seen["header"] = request.get_header("A2a-version")
            seen["method"] = json.loads(request.data)["method"]
            return _FakeResponse({"jsonrpc": "2.0", "id": "1", "result": {}})

        with mock.patch(
            "beacon.protocols.a2a._open", side_effect=fake_urlopen
        ):
            A2AClient("https://fixture.invalid", timeout_seconds=3).send_message("x")
        return seen["header"], seen["method"]

    def test_a_version_declared_only_on_the_interface_is_honoured(self) -> None:
        """
        1.x moved the version statement into each `supportedInterfaces` entry,
        and an SDK generating cards from the current schema need not emit the
        top-level field at all — the Go SDK does not. Reading only the
        top-level made those cards fall back to the constructor default, so an
        interface declaring 0.3 was answered with 1.x method names.
        """
        card = {
            "name": "go-shaped",
            "capabilities": {},
            "skills": [],
            "supportedInterfaces": [
                {
                    "url": "https://fixture.invalid/",
                    "protocolBinding": "JSONRPC",
                    "protocolVersion": "0.3",
                }
            ],
        }
        header, method = self._sent_for_card(card)
        self.assertEqual(header, "0.3")
        self.assertEqual(method, "message/send")

    def test_the_interface_wins_over_a_stale_top_level_field(self) -> None:
        """
        The interface describes the endpoint about to be called; the top-level
        field describes the agent. The more specific claim governs.
        """
        card = {
            "name": "mixed",
            "protocolVersion": "0.3.0",
            "capabilities": {},
            "skills": [],
            "supportedInterfaces": [
                {
                    "url": "https://fixture.invalid/",
                    "protocolBinding": "JSONRPC",
                    "protocolVersion": "1.0",
                }
            ],
        }
        header, method = self._sent_for_card(card)
        self.assertEqual(header, "1.0")
        self.assertEqual(method, "SendMessage")

    def test_an_interface_without_a_version_falls_back_to_the_card(self) -> None:
        card = {
            "name": "partial",
            "protocolVersion": "0.3.0",
            "capabilities": {},
            "skills": [],
            "supportedInterfaces": [
                {"url": "https://fixture.invalid/", "protocolBinding": "JSONRPC"}
            ],
        }
        self.assertEqual(self._sent_for_card(card), ("0.3", "message/send"))

    def test_the_card_fetch_itself_uses_the_default(self) -> None:
        """There is no card yet when the card is being fetched."""
        from beacon.protocols.a2a import A2AClient

        seen: list[str | None] = []

        def fake_urlopen(request: object, timeout: float = 0, context=None):
            del timeout, context
            seen.append(request.get_header("A2a-version"))
            return _FakeResponse(CARD_1X)

        with mock.patch(
            "beacon.protocols.a2a._open", side_effect=fake_urlopen
        ):
            A2AClient("https://fixture.invalid", timeout_seconds=3).discover()
        self.assertEqual(seen, ["1.0"])


class WellKnownPathTests(unittest.TestCase):
    """
    The Agent Card path was renamed: 0.2.x served `/.well-known/agent.json`,
    later revisions serve `/.well-known/agent-card.json`. Deployed agents did
    not all move.

    Two of the live public A2A agents found in a survey answer 404 on the new
    path and 200 on the old one, so Beacon could not see either of them and
    reported "404" as though the agent did not exist.
    """

    def _client_seeing(self, responses: dict[str, object]):
        """`responses` maps a well-known path to a card dict or an HTTP code."""
        import urllib.error

        from beacon.protocols.a2a import A2AClient

        tried: list[str] = []

        def fake_urlopen(request: object, timeout: float = 0, context=None):
            del timeout, context
            url = request.full_url
            tried.append(url)
            for path, outcome in responses.items():
                if url.endswith(path):
                    if isinstance(outcome, int):
                        raise urllib.error.HTTPError(
                            url, outcome, f"HTTP {outcome}", {}, None
                        )
                    return _FakeResponse(outcome)
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        patcher = mock.patch(
            "beacon.protocols.a2a._open", side_effect=fake_urlopen
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return A2AClient("https://fixture.invalid", timeout_seconds=3), tried

    OLD_CARD = {"name": "Legacy agent", "url": "https://fixture.invalid/a2a", "skills": []}

    def test_the_legacy_path_is_tried_when_the_new_one_is_missing(self) -> None:
        client, tried = self._client_seeing(
            {"/.well-known/agent-card.json": 404, "/.well-known/agent.json": self.OLD_CARD}
        )
        self.assertEqual(client.discover()["name"], "Legacy agent")
        self.assertEqual(len(tried), 2)
        self.assertTrue(tried[0].endswith("agent-card.json"))

    def test_the_current_path_wins_and_stops_the_search(self) -> None:
        client, tried = self._client_seeing(
            {"/.well-known/agent-card.json": CARD_1X, "/.well-known/agent.json": self.OLD_CARD}
        )
        self.assertEqual(client.discover()["name"], CARD_1X["name"])
        self.assertEqual(len(tried), 1, "the legacy path was fetched needlessly")

    def test_an_auth_failure_is_not_retried_at_another_path(self) -> None:
        """
        401 is about this endpoint, not about where the card lives. Retrying
        would swap an accurate "you need credentials" for a misleading "no
        card found" naming a path the agent never claimed to serve.
        """
        from beacon.protocols.a2a import A2AError

        for code in (401, 403, 500):
            with self.subTest(code=code):
                client, tried = self._client_seeing(
                    {
                        "/.well-known/agent-card.json": code,
                        "/.well-known/agent.json": self.OLD_CARD,
                    }
                )
                with self.assertRaises(A2AError) as caught:
                    client.discover()
                self.assertIn(str(code), str(caught.exception))
                self.assertEqual(len(tried), 1)

    def test_an_explicit_card_url_is_used_verbatim(self) -> None:
        from beacon.protocols.a2a import A2AClient

        client = A2AClient(
            "https://fixture.invalid/custom/agent.json", timeout_seconds=3
        )
        self.assertEqual(
            client._card_urls(), ("https://fixture.invalid/custom/agent.json",)
        )

    def test_both_paths_missing_reports_the_last_failure(self) -> None:
        from beacon.protocols.a2a import A2AError

        client, tried = self._client_seeing({})
        with self.assertRaises(A2AError):
            client.discover()
        self.assertEqual(len(tried), 2)

    def test_the_path_that_answered_is_recorded(self) -> None:
        client, _ = self._client_seeing(
            {"/.well-known/agent-card.json": 404, "/.well-known/agent.json": self.OLD_CARD}
        )
        client.discover()
        self.assertTrue(str(client.card_url_used).endswith("/.well-known/agent.json"))


if __name__ == "__main__":
    unittest.main()
