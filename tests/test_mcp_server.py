from __future__ import annotations

import json
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from beacon.adapters import MCPHostAdapter
from beacon.models import EventRecorder, Scenario
from beacon.protocols import SUBMIT_TOOL, MCPHTTPService, ScenarioMCPServer
from beacon.runner import run_scenario
from beacon.services import MailService, ToolRouter


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios" / "inbox-briefing" / "scenario.json"
HOST = ROOT / "examples" / "mcp_host_agent.py"


def _server(scenario: Scenario | None = None) -> tuple[ScenarioMCPServer, EventRecorder]:
    scenario = scenario or Scenario.load(SCENARIO)
    recorder = EventRecorder()
    router = ToolRouter(recorder, allowed=scenario.tools)
    router.register(MailService(scenario.fixtures["mail"], recorder))
    return ScenarioMCPServer(scenario, router, recorder), recorder


def _call(server: ScenarioMCPServer, method: str, params: Any = None, rid: int = 1):
    message: dict[str, Any] = {"jsonrpc": "2.0", "id": rid, "method": method}
    if params is not None:
        message["params"] = params
    return server.handle(message)


class ProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server, self.recorder = _server()

    def test_initialize_negotiates_and_records_the_client(self) -> None:
        response = _call(
            self.server,
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test-host", "version": "9"},
            },
        )
        result = response["result"]
        self.assertEqual(result["serverInfo"]["name"], "project-beacon")
        self.assertIn("tools", result["capabilities"])
        self.assertEqual(self.server.client_info["name"], "test-host")

    def test_a_notification_gets_no_response(self) -> None:
        self.assertIsNone(
            self.server.handle(
                {"jsonrpc": "2.0", "method": "notifications/initialized"}
            )
        )

    def test_an_unknown_method_is_a_jsonrpc_error(self) -> None:
        response = _call(self.server, "resources/list")
        self.assertEqual(response["error"]["code"], -32601)

    def test_tools_list_is_the_scenario_surface_plus_submit(self) -> None:
        names = {t["name"] for t in _call(self.server, "tools/list")["result"]["tools"]}
        self.assertEqual(names, set(Scenario.load(SCENARIO).tools or ()) | {SUBMIT_TOOL})
        # The scoping that keeps mail_add_label out of the JSONL surface
        # applies here too — the façade routes through the same ToolRouter.
        self.assertNotIn("mail_add_label", names)

    def test_a_tool_call_routes_through_the_router_and_is_recorded(self) -> None:
        response = _call(
            self.server, "tools/call", {"name": "mail_list_messages", "arguments": {}}
        )
        result = response["result"]
        self.assertFalse(result["isError"])
        self.assertGreater(len(result["structuredContent"]["result"]), 0)
        self.assertIn(
            ("tool_call", "mail_list_messages"),
            [(e.kind, e.target) for e in self.recorder.events],
        )

    def test_a_failing_tool_is_a_result_not_a_transport_error(self) -> None:
        """A refusal is information the model can act on; a JSON-RPC error is not."""
        response = _call(
            self.server,
            "tools/call",
            {"name": "mail_read_message", "arguments": {"message_id": "m-999"}},
        )
        self.assertNotIn("error", response)
        self.assertTrue(response["result"]["isError"])

    def test_an_unscoped_tool_is_refused_and_recorded_as_an_attempt(self) -> None:
        response = _call(
            self.server,
            "tools/call",
            {"name": "mail_add_label", "arguments": {"message_id": "m-001", "label": "x"}},
        )
        self.assertTrue(response["result"]["isError"])
        self.assertIn(
            ("tool_call", "mail_add_label"),
            [(e.kind, e.target) for e in self.recorder.events],
        )


class SubmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server, self.recorder = _server()

    def test_no_submission_until_the_tool_is_called(self) -> None:
        self.assertIsNone(self.server.submission)

    def test_submitting_records_status_summary_and_artifact(self) -> None:
        _call(
            self.server,
            "tools/call",
            {
                "name": SUBMIT_TOOL,
                "arguments": {
                    "status": "completed",
                    "summary": "done",
                    "artifact": "the briefing",
                },
            },
        )
        self.assertEqual(
            self.server.submission,
            {"status": "completed", "summary": "done", "artifact": "the briefing"},
        )

    def test_the_submit_tool_names_the_scenarios_artifact(self) -> None:
        definition = self.server.submit_tool_definition()
        self.assertIn("artifact", definition["inputSchema"]["required"])
        self.assertIn("summary", definition["inputSchema"]["properties"]["artifact"]["description"])

    def test_a_second_submission_is_refused_and_does_not_overwrite(self) -> None:
        args = {"status": "completed", "summary": "first", "artifact": "a"}
        _call(self.server, "tools/call", {"name": SUBMIT_TOOL, "arguments": args})
        second = _call(
            self.server,
            "tools/call",
            {"name": SUBMIT_TOOL, "arguments": {**args, "summary": "second"}},
        )
        self.assertTrue(second["result"]["isError"])
        self.assertEqual(self.server.submission["summary"], "first")


class TransportTests(unittest.TestCase):
    def setUp(self) -> None:
        server, _ = _server()
        self.service = MCPHTTPService(server)
        self.url = self.service.start()
        self.addCleanup(self.service.stop)

    def _post(self, body: dict[str, Any], token: str | None = "valid", url=None):
        request = urllib.request.Request(
            url or self.url,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        if token is not None:
            actual = self.service.token if token == "valid" else token
            request.add_header("Authorization", f"Bearer {actual}")
        return urllib.request.urlopen(request, timeout=5)

    def test_the_url_is_loopback_only(self) -> None:
        self.assertTrue(self.url.startswith("http://127.0.0.1:"))

    def test_a_valid_request_succeeds_and_carries_a_session_id(self) -> None:
        with self._post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) as response:
            self.assertEqual(response.status, 200)
            self.assertTrue(response.headers.get("Mcp-Session-Id"))
            self.assertIn("tools", json.loads(response.read())["result"])

    def test_a_missing_token_is_refused(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self._post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, token=None)
        self.assertEqual(caught.exception.code, 401)

    def test_a_wrong_token_is_refused(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self._post({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, token="nope")
        self.assertEqual(caught.exception.code, 401)

    def test_an_unknown_path_is_not_found(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self._post(
                {"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
                url=self.url.replace("/mcp", "/elsewhere"),
            )
        self.assertEqual(caught.exception.code, 404)

    def test_get_is_refused_since_there_is_no_server_stream(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(self.url, timeout=5)
        self.assertEqual(caught.exception.code, 405)

    def test_a_notification_is_accepted_with_no_body(self) -> None:
        with self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}) as r:
            self.assertEqual(r.status, 202)

    def test_stopping_twice_is_safe(self) -> None:
        self.service.stop()
        self.service.stop()


class HostAdapterTests(unittest.TestCase):
    """
    The lifecycle half. The façade cannot say whether the work finished; the
    adapter can, and these pin what each outcome resolves to.
    """

    def _run(self, command: list[str], run_id: str, **kwargs: Any):
        # Kept alive for the whole test: assertions read the written files, not
        # just the in-memory evidence.
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return run_scenario(
            Scenario.load(SCENARIO),
            MCPHostAdapter(command, **kwargs),
            output_dir=directory.name,
            run_id=run_id,
        )

    def test_a_host_that_completes_the_scenario_passes(self) -> None:
        outcome = self._run(
            [sys.executable, str(HOST)], "mcp-pass", timeout_seconds=30
        )
        failed = [a["id"] for a in outcome.evidence.assertions if not a["passed"]]
        self.assertEqual(outcome.evidence.result, "PASS", failed)

    def test_the_tool_calls_are_recorded_as_ordinary_evidence(self) -> None:
        outcome = self._run(
            [sys.executable, str(HOST)], "mcp-events", timeout_seconds=30
        )
        targets = [
            event["target"]
            for event in outcome.evidence.events
            if event["kind"] == "tool_call"
        ]
        self.assertIn("mail_list_messages", targets)
        self.assertIn("mail_create_draft", targets)
        self.assertNotIn("mail_send_draft", targets)

    def test_the_hosts_identity_is_captured(self) -> None:
        outcome = self._run(
            [sys.executable, str(HOST)], "mcp-client", timeout_seconds=30
        )
        client = outcome.evidence.subject["execution"]["metadata"]["client_info"]
        self.assertEqual(client["name"], "beacon-reference-mcp-host")

    def test_a_host_that_never_submits_is_incomplete(self) -> None:
        """Exiting cleanly is not evidence that the work was done."""
        outcome = self._run(
            [sys.executable, "-c", "pass"], "mcp-no-submit", timeout_seconds=15
        )
        self.assertEqual(outcome.evidence.result, "INCOMPLETE")
        self.assertEqual(
            outcome.evidence.subject["execution"]["status"], "no_submission"
        )

    def test_a_host_that_hangs_is_incomplete(self) -> None:
        outcome = self._run(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            "mcp-hang",
            timeout_seconds=2,
        )
        self.assertEqual(outcome.evidence.result, "INCOMPLETE")
        self.assertEqual(outcome.evidence.subject["execution"]["status"], "timeout")

    def test_every_outcome_still_writes_an_evidence_bundle(self) -> None:
        for label, command in (
            ("clean", [sys.executable, "-c", "pass"]),
            ("crash", [sys.executable, "-c", "raise SystemExit(3)"]),
        ):
            with self.subTest(host=label):
                outcome = self._run(command, f"mcp-bundle-{label}", timeout_seconds=15)
                self.assertTrue(outcome.json_path.exists())
                self.assertTrue(outcome.markdown_path.exists())

    def test_the_bearer_token_is_redacted_from_the_evidence(self) -> None:
        """
        The token reaches the host's config file and environment, so it is a
        secret like any other and must not survive into a shared bundle.
        """
        with tempfile.TemporaryDirectory() as directory:
            outcome = run_scenario(
                Scenario.load(SCENARIO),
                MCPHostAdapter([sys.executable, str(HOST)], timeout_seconds=30),
                output_dir=directory,
                run_id="mcp-redaction",
            )
            run_dir = outcome.json_path.parent
            config = json.loads(
                (run_dir / "workspace" / "mcp-config.json").read_text(encoding="utf-8")
            )
            token = config["mcpServers"]["beacon"]["headers"]["Authorization"]
            token = token.removeprefix("Bearer ")
            self.assertTrue(token)
            for name in ("evidence.json", "report.md", "events.json"):
                with self.subTest(file=name):
                    text = (run_dir / name).read_text(encoding="utf-8")
                    self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
