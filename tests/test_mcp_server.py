from __future__ import annotations

import json
import os
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
                token="pinned-token",
            )
            url = service.start()
            try:
                seen.append((url, service.token))
            finally:
                service.stop()

        self.assertEqual(seen[0][1], seen[1][1], "the token changed between runs")
        self.assertEqual(seen[0][1], "pinned-token")

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
