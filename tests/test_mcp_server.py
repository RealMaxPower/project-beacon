from __future__ import annotations

import json
import os
import socket
import stat
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from beacon.adapters import MCPHostAdapter
from beacon.models import EventRecorder, Scenario
from beacon.protocols import (
    MINIMUM_TOKEN_LENGTH,
    SUBMIT_TOOL,
    MCPHTTPService,
    ScenarioMCPServer,
)
from beacon.protocols.mcp_server import MAX_BODY_BYTES
from beacon.runner import run_scenario
from beacon.services import MailService, ToolRouter


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios" / "inbox-briefing" / "scenario.json"
# Long enough to clear `MINIMUM_TOKEN_LENGTH`. The fixture used to read
# "pinned-token", which the floor now refuses — a twelve-character credential
# in front of a live tool façade is precisely what it exists to stop.
PINNED_TOKEN = "pinned-token-for-two-runs"
HOST = ROOT / "examples" / "mcp_host_agent.py"
SLOW_TEARDOWN_HOST = ROOT / "examples" / "mcp_host_slow_teardown.py"


def _server(scenario: Scenario | None = None) -> tuple[ScenarioMCPServer, EventRecorder]:
    scenario = scenario or Scenario.load(SCENARIO)
    recorder = EventRecorder()
    router = ToolRouter(recorder, allowed=scenario.tools)
    router.register(MailService(scenario.fixtures["mail"], recorder))
    return ScenarioMCPServer(scenario, router, recorder), recorder


def _narrowly_scoped() -> Scenario:
    """
    The starter scenario cut down to one tool, so there is always an out-of-
    scope tool to attempt.

    It used to be enough to name `mail_add_label`, which the scenario kept off
    its surface. That stopped being true when the tool was put back with an
    explicit prohibition in the goal, and these tests would have silently
    become assertions about nothing.
    """
    value = json.loads(SCENARIO.read_text(encoding="utf-8"))
    value["tools"] = ["mail_list_messages"]
    return Scenario.from_dict(value)


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

    def test_a_narrowed_scope_is_honoured_over_the_facade(self) -> None:
        """
        Scoping is a property of the router, which the façade shares with the
        JSONL surface. Built from a deliberately narrow scope rather than from
        whatever the shipped scenario happens to declare, so re-admitting a
        tool there cannot quietly empty this test.
        """
        server, _ = _server(_narrowly_scoped())
        names = {t["name"] for t in _call(server, "tools/list")["result"]["tools"]}
        self.assertEqual(names, {"mail_list_messages", SUBMIT_TOOL})

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
        server, self.recorder = _server(_narrowly_scoped())
        response = _call(
            server,
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

    def _raw(self, headers: str, body: bytes = b"") -> bytes:
        """
        Speak HTTP by hand.

        `urllib` computes Content-Length itself and will not send a malformed
        one, so the header this class is about cannot be tested through it.
        """
        host, port = self.service._httpd.server_address[:2]
        connection = socket.create_connection((host, port), timeout=5)
        self.addCleanup(connection.close)
        # latin-1, not ascii: header bytes are latin-1 on the wire, and one of
        # the cases below is a non-ascii character that `str.isdigit` calls a
        # digit. Encoding as ascii would fail in the test rather than at the
        # server, and prove nothing about the server.
        connection.sendall(headers.encode("latin-1") + b"\r\n" + body)
        connection.settimeout(5)
        try:
            return connection.recv(200)
        except socket.timeout:
            return b""

    def _headers(self, length: str) -> str:
        return (
            f"POST /mcp HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Authorization: Bearer {self.service.token}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {length}\r\n"
        )

    def test_a_negative_content_length_is_refused(self) -> None:
        """
        `int()` accepts "-1". It then passes the size cap, and `read(-1)` reads
        until the client closes — so the one check that bounds how much memory
        a request may claim was bypassed by writing a minus sign, and the
        handler thread blocked for as long as the caller cared to hold it.
        """
        self.assertIn(b"400", self._raw(self._headers("-1")))

    def test_a_content_length_that_is_not_ascii_digits_is_refused(self) -> None:
        # `"²".isdigit()` is True, which is why the ascii test comes first.
        for length in ("-1", "+5", "1_0", "", " ", "1.5", "²"):
            with self.subTest(length=length):
                self.assertIn(b"400", self._raw(self._headers(length)))

    def test_an_oversized_declared_body_is_refused(self) -> None:
        answer = self._raw(self._headers(str(MAX_BODY_BYTES + 1)))
        self.assertIn(b"413", answer)

    def test_a_body_at_the_cap_is_still_read(self) -> None:
        """The cap must refuse the oversized, not the merely large."""
        message = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
        body = json.dumps(message).encode()
        answer = self._raw(self._headers(str(len(body))), body)
        self.assertIn(b"200", answer)

    def test_the_handler_carries_a_socket_timeout(self) -> None:
        """
        Without one, a connection that opens and says nothing holds its thread
        for the life of the process, and nothing caps the thread count — so
        the façade can be tied up without presenting the token at all.
        """
        handler = self.service._httpd.RequestHandlerClass
        self.assertIsNotNone(handler.timeout)
        self.assertGreater(handler.timeout, 0)


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
        # A host that never submitted was not terminated after completing
        # anything. The two timeout paths have to stay tellable apart, or the
        # key below stops meaning what it says.
        self.assertNotIn(
            "terminated_after_complete",
            outcome.evidence.subject["execution"]["metadata"],
        )

    def test_a_host_that_submits_and_then_hangs_still_gets_a_verdict(self) -> None:
        """
        The rule the JSONL adapter already states, applied to this protocol:
        nothing that happens after a completion was validly sent can retract
        it. This used to resolve INCOMPLETE, discarding an artifact Beacon had
        already recorded and graded.
        """
        outcome = self._run(
            [sys.executable, str(SLOW_TEARDOWN_HOST)],
            "mcp-submit-then-hang",
            timeout_seconds=25,
        )
        failed = [a["id"] for a in outcome.evidence.assertions if not a["passed"]]
        self.assertEqual(outcome.evidence.result, "PASS", failed)
        self.assertEqual(outcome.evidence.subject["execution"]["status"], "completed")
        self.assertIn("summary", outcome.evidence.artifacts)

    def test_the_termination_is_recorded_even_though_the_verdict_stands(self) -> None:
        """
        The other half, and the one that stops the fix above from becoming
        "quietly forgive timeouts". A PASS on a run Beacon had to kill has to
        say so — in the metadata, in the event stream, and in report.md, which
        is the only one of the three most people read.
        """
        outcome = self._run(
            [sys.executable, str(SLOW_TEARDOWN_HOST)],
            "mcp-submit-then-hang-recorded",
            timeout_seconds=25,
        )
        self.assertTrue(
            outcome.evidence.subject["execution"]["metadata"][
                "terminated_after_complete"
            ]
        )
        completed = [
            event
            for event in outcome.evidence.events
            if event["kind"] == "subject_completed"
        ]
        self.assertEqual(len(completed), 1)
        self.assertTrue(completed[0]["payload"]["timed_out"])
        self.assertTrue(completed[0]["payload"]["submitted"])
        self.assertTrue(
            any("terminated it" in item for item in outcome.evidence.limitations),
            outcome.evidence.limitations,
        )
        self.assertIn("terminated it", outcome.markdown_path.read_text(encoding="utf-8"))

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

    @unittest.skipIf(
        os.name == "nt",
        "Windows has no POSIX mode to assert: os.chmod there only toggles the "
        "read-only bit, and the file's protection comes from directory ACLs.",
    )
    def test_the_config_holding_the_token_is_not_world_readable(self) -> None:
        """
        Redaction covers the bundle, not the config file beside it. That file
        holds the only credential guarding the tool facade — including
        `beacon_submit`, which decides the recorded verdict — so a second
        account on the machine must not be able to read it.
        """
        with tempfile.TemporaryDirectory() as directory:
            outcome = run_scenario(
                Scenario.load(SCENARIO),
                MCPHostAdapter([sys.executable, str(HOST)], timeout_seconds=30),
                output_dir=directory,
                run_id="mcp-config-mode",
            )
            config = outcome.json_path.parent / "workspace" / "mcp-config.json"
            mode = stat.S_IMODE(config.stat().st_mode)
            self.assertEqual(mode, 0o600, f"config is {oct(mode)}, not 0600")


if __name__ == "__main__":
    unittest.main()


class ServeAdapterInterruptionTests(unittest.TestCase):
    """
    `MCPServeAdapter` waits for a host somebody else connects, so the run ends
    when a person decides it does. It already returned the right verdict for a
    Ctrl-C that arrived after the submission — the wait loop exits on the
    submission, not the key — but the subject record carried only
    `client_info`, so that run was indistinguishable from an untouched one
    everywhere except the event payload.

    The interruption is driven here by standing in for the wait itself, which
    is the only part of this adapter a test can reach without a human at a
    keyboard. The submission is made over the real transport.
    """

    def _submit(self, config_path: Path) -> None:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        server = config["mcpServers"]["beacon"]
        request = urllib.request.Request(
            server["url"],
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": SUBMIT_TOOL,
                        "arguments": {
                            "status": "completed",
                            "summary": "Prepared 2 draft responses.",
                            "artifact": "Action-required inbox briefing",
                        },
                    },
                }
            ).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": server["headers"]["Authorization"],
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 200)

    def _run_interrupted_after_submitting(self, run_id: str):
        from unittest import mock

        from beacon.adapters import MCPServeAdapter

        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        config_path = (
            Path(directory.name) / run_id / "workspace" / "mcp-config.json"
        )
        def fake_wait(_seconds: float) -> None:
            # Both in the one wait, which is the only ordering that reaches
            # this branch: the loop re-checks `submission` as soon as it wakes,
            # so a Ctrl-C after that check ends a run that has already left the
            # loop. The race the adapter has to survive is a person stopping a
            # run in the moment the result lands.
            self._submit(config_path)
            raise KeyboardInterrupt

        with mock.patch("beacon.adapters.mcp_host.time.sleep", fake_wait):
            outcome = run_scenario(
                Scenario.load(SCENARIO),
                MCPServeAdapter(timeout_seconds=30, announce=lambda *_: None),
                output_dir=directory.name,
                run_id=run_id,
            )
        return outcome

    def test_a_result_submitted_before_a_ctrl_c_is_not_discarded(self) -> None:
        outcome = self._run_interrupted_after_submitting("serve-interrupted")
        self.assertEqual(outcome.evidence.subject["execution"]["status"], "completed")
        self.assertNotEqual(outcome.evidence.result, "INCOMPLETE")

    def test_the_interruption_is_recorded_even_though_the_verdict_stands(self) -> None:
        outcome = self._run_interrupted_after_submitting("serve-interrupted-recorded")
        self.assertTrue(
            outcome.evidence.subject["execution"]["metadata"][
                "terminated_after_complete"
            ]
        )
        self.assertTrue(
            any("stopped by hand" in item for item in outcome.evidence.limitations),
            outcome.evidence.limitations,
        )

    def test_an_untouched_run_says_so(self) -> None:
        """
        The mirror. Without it, a flag that was always True would pass both
        tests above and record nothing.
        """
        from unittest import mock

        from beacon.adapters import MCPServeAdapter

        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        config_path = (
            Path(directory.name) / "serve-clean" / "workspace" / "mcp-config.json"
        )

        with mock.patch(
            "beacon.adapters.mcp_host.time.sleep",
            lambda _s: self._submit(config_path),
        ):
            outcome = run_scenario(
                Scenario.load(SCENARIO),
                MCPServeAdapter(timeout_seconds=30, announce=lambda *_: None),
                output_dir=directory.name,
                run_id="serve-clean",
            )
        self.assertFalse(
            outcome.evidence.subject["execution"]["metadata"][
                "terminated_after_complete"
            ]
        )
        self.assertFalse(
            [item for item in outcome.evidence.limitations if "stopped by hand" in item]
        )


class PinnedFacadeTests(unittest.TestCase):
    """
    A GUI host is configured by hand. With an ephemeral port and a fresh token
    per run, the stored connector is stale before the second run starts, which
    is enough friction to stop anyone trying the desktop flow twice.
    """

    def test_a_pinned_port_and_token_survive_two_runs(self) -> None:
        scenario = Scenario.load(SCENARIO)
        seen: list[tuple[str, str]] = []

        for index in range(2):
            recorder = EventRecorder()
            router = ToolRouter(recorder, allowed=scenario.tools)
            router.register(MailService(scenario.fixtures["mail"], recorder))
            service = MCPHTTPService(
                ScenarioMCPServer(scenario, router, recorder),
                port=0 if index else 0,
                token=PINNED_TOKEN,
            )
            url = service.start()
            try:
                seen.append((url, service.token))
            finally:
                service.stop()

        self.assertEqual(seen[0][1], seen[1][1], "the token changed between runs")
        self.assertEqual(seen[0][1], PINNED_TOKEN)

    def test_an_unpinned_token_is_different_every_run(self) -> None:
        """The default must stay ephemeral; pinning is opt-in."""
        scenario = Scenario.load(SCENARIO)
        tokens = set()
        for _ in range(2):
            recorder = EventRecorder()
            router = ToolRouter(recorder, allowed=scenario.tools)
            router.register(MailService(scenario.fixtures["mail"], recorder))
            service = MCPHTTPService(ScenarioMCPServer(scenario, router, recorder))
            service.start()
            tokens.add(service.token)
            service.stop()
        self.assertEqual(len(tokens), 2)

    def test_a_pinned_token_below_the_floor_is_refused(self) -> None:
        """
        The generated token is 32 random bytes; the supplied one was checked
        only for being non-empty, so `BEACON_MCP_TOKEN=test` was accepted — and
        that token is the whole of what stands between another account on the
        machine and `beacon_submit`, which decides the recorded verdict.
        """
        scenario = Scenario.load(SCENARIO)
        recorder = EventRecorder()
        router = ToolRouter(recorder, allowed=scenario.tools)
        router.register(MailService(scenario.fixtures["mail"], recorder))
        server = ScenarioMCPServer(scenario, router, recorder)
        with self.assertRaises(ValueError) as caught:
            MCPHTTPService(server, token="a" * (MINIMUM_TOKEN_LENGTH - 1))
        self.assertIn(str(MINIMUM_TOKEN_LENGTH), str(caught.exception))

    def test_the_cli_refuses_a_token_variable_below_the_floor(self) -> None:
        """
        Refused by name and before a run directory exists, rather than as an
        anonymous ValueError from inside a run that has already started.
        """
        from beacon.cli import main

        variable = "BEACON_TEST_SHORT_TOKEN_VAR"
        os.environ[variable] = "short"
        self.addCleanup(os.environ.pop, variable, None)
        with tempfile.TemporaryDirectory() as directory:
            code = main(
                ["serve-mcp", str(SCENARIO), "--output", directory,
                 "--token-env", variable]
            )
        self.assertEqual(code, 2)

    def test_the_cli_refuses_an_unset_token_variable(self) -> None:
        """
        Silently generating a random token would leave the operator staring at
        a host that cannot connect, with nothing saying why.
        """
        from beacon.cli import main

        with tempfile.TemporaryDirectory() as directory:
            code = main(
                [
                    "serve-mcp",
                    str(SCENARIO),
                    "--output",
                    directory,
                    "--token-env",
                    "BEACON_DEFINITELY_UNSET_TOKEN_VAR",
                ]
            )
        self.assertEqual(code, 2)

    def test_a_scenario_pack_can_be_served_to_a_host(self) -> None:
        """
        `run` and `validate` both took `--service-module`; `serve-mcp` did not.
        So a pack that brings its own service — the thing that proves a third
        party needs no changes under `beacon/` — could be run headless and
        never handed to a GUI host, which is the one flow a person is needed
        for. It failed with "scenario scopes tools but defines no supported
        service fixture", naming the fixture rather than the missing flag.
        """
        from beacon.cli import main
        from beacon.services import registry

        # The registry is process-global and `--service-module` registers into
        # it permanently. `tests/test_scenario_pack.py` runs the pack in a
        # subprocess for exactly this reason; this test drives the CLI in
        # process, so it has to put the registry back or it silently changes
        # what every later test sees.
        before = set(registry._FACTORIES)
        self.addCleanup(
            lambda: [
                registry._FACTORIES.pop(name, None)
                for name in set(registry._FACTORIES) - before
            ]
        )

        pack = ROOT / "examples" / "scenario-pack"
        with tempfile.TemporaryDirectory() as directory:
            code = main(
                [
                    "serve-mcp",
                    str(pack / "scenario.json"),
                    "--service-module",
                    str(pack / "service.py"),
                    "--output",
                    directory,
                    "--timeout",
                    "0.2",
                ]
            )
        # INCOMPLETE, because nobody connected — but it served, which is the
        # point. Without the flag this raised before the server ever started.
        self.assertEqual(code, 1)

    def test_serving_a_pack_without_its_module_still_explains_itself(self) -> None:
        """
        The flag must be the fix, not a silent default that hides the need.

        The registry is process-global and registration is not undone, so the
        test above leaves `support` registered and this one would pass for the
        wrong reason — it would be measuring test order rather than behaviour.
        Clearing it first is what makes the check mean anything.
        """
        from beacon.cli import main
        from beacon.services import registry

        removed = registry._FACTORIES.pop("support", None)
        if removed is not None:
            self.addCleanup(registry._FACTORIES.__setitem__, "support", removed)

        pack = ROOT / "examples" / "scenario-pack"
        with tempfile.TemporaryDirectory() as directory:
            code = main(
                ["serve-mcp", str(pack / "scenario.json"), "--output", directory]
            )
        self.assertEqual(code, 2)
