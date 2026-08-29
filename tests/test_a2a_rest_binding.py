from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from beacon.adapters import A2ASubjectAdapter
from beacon.models import Scenario
from beacon.protocols.a2a import A2AClient, A2AError
from beacon.runner import run_scenario


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios" / "hosted-injection-resistance" / "scenario.json"

REST_CARD = {
    "name": "HTTP+JSON agent",
    "description": "Declares the binding the REST branch exists to serve.",
    "version": "1.0.0",
    "supportedInterfaces": [
        {
            "url": "http://fixture.invalid/",
            "protocolBinding": "HTTP+JSON",
            "protocolVersion": "1.0",
        }
    ],
    "capabilities": {"streaming": False},
    "defaultInputModes": ["text"],
    "defaultOutputModes": ["text"],
    "skills": [{"id": "echo", "name": "echo", "description": "d", "tags": []}],
}

BARE_TASK = {
    "id": "task-1",
    "status": {"state": "completed"},
    "artifacts": [
        {
            "name": "answer",
            "parts": [{"text": "Project Atlas enters phase two in October."}],
        }
    ],
}


class _FakeResponse:
    def __init__(self, value: dict) -> None:
        self._payload = json.dumps(value).encode("utf-8")
        self.headers = {"Content-Length": str(len(self._payload))}
        self.status = 200

    def read(self, amount: int = -1) -> bytes:
        payload, self._payload = self._payload, b""
        return payload if amount < 0 else payload[:amount]

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None


def _serving(reply: dict, card: dict = REST_CARD):
    def fake_urlopen(request: object, timeout: float = 0, context=None):
        del timeout, context
        if "agent-card" in request.full_url or "agent.json" in request.full_url:
            return _FakeResponse(card)
        return _FakeResponse(reply)

    return mock.patch("beacon.protocols.a2a._open", side_effect=fake_urlopen)


class RestEnvelopeTests(unittest.TestCase):
    """
    The HTTP+JSON binding answers with the bare Task; JSON-RPC wraps it in
    `result`. The adapter reads `response.get("result")` once for both, so a
    REST reply resolved to `{}` — no state, no artifacts — and a healthy agent
    was graded `unknown_state`, which is an *unobserved* ending and therefore
    INCOMPLETE.

    The same agent over two bindings got two verdicts, and the one that lost is
    the binding this branch exists to serve. It survived because every
    adapter-level test wrapped its reply in a JSON-RPC envelope regardless of
    the card, and the one REST test asserted only the URL.
    """

    def _run(self, reply: dict, card: dict = REST_CARD):
        with _serving(reply, card), tempfile.TemporaryDirectory() as directory:
            return run_scenario(
                Scenario.load(SCENARIO),
                A2ASubjectAdapter("http://fixture.invalid", timeout_seconds=5),
                output_dir=directory,
                run_id="rest",
            )

    def test_a_bare_task_is_graded_rather_than_reported_unknown(self) -> None:
        outcome = self._run(BARE_TASK)
        self.assertNotEqual(
            outcome.evidence.subject["execution"]["status"],
            "unknown_state",
            "a healthy REST agent was graded as an ending nobody observed",
        )
        self.assertNotEqual(outcome.evidence.result, "INCOMPLETE")

    def test_the_artifacts_of_a_bare_task_are_not_dropped(self) -> None:
        """
        The half that makes the verdict meaningless rather than merely wrong:
        with no `result`, `_store_artifacts` was handed `{}` and recorded
        nothing, so there was nothing left to grade.
        """
        outcome = self._run(BARE_TASK)
        self.assertTrue(
            outcome.evidence.artifacts,
            "the agent returned an artifact and the bundle recorded none",
        )

    def test_a_bare_message_reply_is_also_carried(self) -> None:
        """A Message is the whole reply for an agent with no work to track."""
        outcome = self._run(
            {
                "message": {
                    "messageId": "m-1",
                    "role": "ROLE_AGENT",
                    "parts": [{"text": "Phase two, October."}],
                }
            }
        )
        self.assertNotEqual(outcome.evidence.result, "INCOMPLETE")


class RestEnvelopePassthroughTests(unittest.TestCase):
    """A reply that is already wrapped must not be wrapped twice."""

    def _send(self, reply: dict) -> dict:
        with _serving(reply):
            client = A2AClient("http://fixture.invalid", timeout_seconds=5)
            client.discover()
            return client.send_message("hello")

    def test_a_bare_task_is_wrapped(self) -> None:
        self.assertEqual(self._send(BARE_TASK), {"result": BARE_TASK})

    def test_an_already_enveloped_reply_is_untouched(self) -> None:
        enveloped = {"jsonrpc": "2.0", "id": "1", "result": BARE_TASK}
        self.assertEqual(self._send(enveloped), enveloped)

    def test_a_task_keyed_reply_is_untouched(self) -> None:
        """
        `{"task": ...}` is a third shape the adapter has always read, and
        wrapping it broke `test_protocols.A2ATests` — which is how it was found.
        """
        keyed = {"task": BARE_TASK}
        self.assertEqual(self._send(keyed), keyed)

    def test_an_error_body_returned_with_200_is_raised(self) -> None:
        """
        The JSON-RPC branch checks for this and the REST branch did not, so an
        error body was read as a successful result and graded as the agent's
        answer.
        """
        with self.assertRaises(A2AError):
            self._send({"error": {"code": -32000, "message": "upstream failed"}})

    def test_a_non_object_reply_is_refused(self) -> None:
        with self.assertRaises(A2AError):
            self._send(["not", "an", "object"])


if __name__ == "__main__":
    unittest.main()
