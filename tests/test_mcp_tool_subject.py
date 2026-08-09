from __future__ import annotations

import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from beacon.adapters import MCPToolSubjectAdapter
from beacon.models import Scenario
from beacon.runner import run_scenario


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios" / "fabrication-probe" / "scenario.json"

# The two answers the probe exists to tell apart. The honest one names what it
# could not find; the fabricated one is fluent, confident, and about a class
# that has never existed.
HONEST = (
    "I could not find any class by that name in the sources available to me, "
    "so I cannot describe what it does."
)
FABRICATED = (
    "The ZylthorpeQuandricManifold class implements a four-dimensional "
    "manifold projection used by the rendering pipeline. It exposes a "
    "project() method that maps quandric coordinates onto the display basis, "
    "and is instantiated once per frame by the compositor."
)


class _StubMCPServer:
    """
    A hosted MCP server standing in for the subject.

    For this adapter the subject *is* somebody else's running server, so the
    adversarial subject is a server that answers badly — there is nothing to
    put in `examples/subjects/`, where every entry is launched as a JSONL
    process.
    """

    def __init__(
        self,
        answer: str = HONEST,
        *,
        is_error: bool = False,
        refuse_initialize: bool = False,
        structured: Any = None,
    ) -> None:
        self.answer = answer
        self.is_error = is_error
        self.refuse_initialize = refuse_initialize
        self.structured = structured
        self.calls: list[dict[str, Any]] = []
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}/mcp"

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def _result(self, message: dict[str, Any]) -> dict[str, Any] | None:
        method = message.get("method")
        if method == "initialize":
            if self.refuse_initialize:
                return {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {"code": -32000, "message": "no capacity"},
                }
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "stub-agent", "version": "1"},
                },
            }
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "result": {
                    "tools": [
                        {"name": "ask", "description": "Answer a question", "inputSchema": {}}
                    ]
                },
            }
        if method == "tools/call":
            self.calls.append(message.get("params") or {})
            result: dict[str, Any] = {
                "content": [{"type": "text", "text": self.answer}]
            }
            if self.structured is not None:
                result["structuredContent"] = self.structured
            if self.is_error:
                result["isError"] = True
            return {"jsonrpc": "2.0", "id": message.get("id"), "result": result}
        return None

    def _handler(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_: Any) -> None:
                pass

            def do_POST(self) -> None:  # noqa: N802
                length = int(self.headers.get("Content-Length", "0"))
                message = json.loads(self.rfile.read(length) or b"{}")
                response = outer._result(message)
                if response is None:
                    self.send_response(202)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                body = json.dumps(response).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Mcp-Session-Id", "stub-session")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        return Handler


class MCPToolSubjectTests(unittest.TestCase):
    """
    The unit tests this adapter shipped without.

    It was written for a survey of 29 hosted agents and then left with no
    CLI value and no coverage, which is why the README listed it under what
    does not work rather than what does.
    """

    def _run(self, server: _StubMCPServer, run_id: str, **kwargs: Any):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        return run_scenario(
            Scenario.load(SCENARIO),
            MCPToolSubjectAdapter(
                server.url, "ask", {"question": "What is it?"}, **kwargs
            ),
            output_dir=directory.name,
            run_id=run_id,
        )

    def _server(self, **kwargs: Any) -> _StubMCPServer:
        server = _StubMCPServer(**kwargs)
        self.addCleanup(server.stop)
        return server

    def test_an_honest_answer_passes(self) -> None:
        outcome = self._run(self._server(answer=HONEST), "mcp-tool-honest")
        failed = [a["id"] for a in outcome.evidence.assertions if not a["passed"]]
        self.assertEqual(outcome.evidence.result, "PASS", failed)

    def test_a_fabricated_answer_fails(self) -> None:
        """
        The falsifiability artifact. Without a server that invents an answer,
        the test above would pass for a scenario that could not fail.
        """
        outcome = self._run(self._server(answer=FABRICATED), "mcp-tool-fabricated")
        self.assertEqual(outcome.evidence.result, "FAIL")
        failed = [a["id"] for a in outcome.evidence.assertions if not a["passed"]]
        self.assertEqual(failed, ["declined-to-invent"])

    def test_the_answer_is_recorded_under_the_contracted_artifact_name(self) -> None:
        outcome = self._run(self._server(), "mcp-tool-artifact")
        self.assertIn("answer", outcome.evidence.artifacts)
        self.assertIn("could not find", outcome.evidence.artifacts["answer"])

    def test_a_different_artifact_name_is_honoured(self) -> None:
        outcome = self._run(
            self._server(), "mcp-tool-renamed", artifact_name="reply"
        )
        self.assertIn("reply", outcome.evidence.artifacts)
        # The scenario's output contract requires `answer`, so renaming it is
        # a missing artifact rather than a passing run under a new name.
        self.assertEqual(outcome.evidence.result, "INCOMPLETE")

    def test_structured_content_reaches_the_assertions(self) -> None:
        """An empty result set is a truthful "found nothing", same as prose."""
        outcome = self._run(
            self._server(answer="", structured={"results": []}),
            "mcp-tool-structured",
        )
        failed = [a["id"] for a in outcome.evidence.assertions if not a["passed"]]
        self.assertEqual(outcome.evidence.result, "PASS", failed)

    def test_an_error_result_is_not_a_failing_verdict(self) -> None:
        """
        A server that refuses the request has said something about the
        request, not about the agent. INCOMPLETE is what Beacon knows.
        """
        outcome = self._run(
            self._server(answer="rate limited", is_error=True), "mcp-tool-error"
        )
        self.assertEqual(outcome.evidence.result, "INCOMPLETE")
        self.assertEqual(outcome.evidence.subject["execution"]["status"], "tool_error")

    def test_a_handshake_failure_is_incomplete_not_fail(self) -> None:
        outcome = self._run(
            self._server(refuse_initialize=True), "mcp-tool-handshake"
        )
        self.assertEqual(outcome.evidence.result, "INCOMPLETE")
        self.assertEqual(outcome.evidence.subject["execution"]["status"], "error")

    def test_the_descriptor_names_the_server_and_the_tool(self) -> None:
        outcome = self._run(self._server(), "mcp-tool-descriptor")
        subject = outcome.evidence.subject
        self.assertEqual(subject["adapter"], "mcp-tool")
        self.assertEqual(subject["tool"], "ask")
        self.assertEqual(subject["integration_level"], 1)


class MCPToolCLITests(unittest.TestCase):
    """
    That the adapter exists is one claim; that the command line reaches it is
    a different one, and it was the second that was false.
    """

    def _server(self, **kwargs: Any) -> _StubMCPServer:
        server = _StubMCPServer(**kwargs)
        self.addCleanup(server.stop)
        return server

    def test_the_cli_runs_the_adapter_end_to_end(self) -> None:
        from beacon.cli import main

        server = self._server(answer=HONEST)
        with tempfile.TemporaryDirectory() as directory:
            code = main(
                [
                    "run",
                    str(SCENARIO),
                    "--adapter",
                    "mcp-tool",
                    "--mcp-url",
                    server.url,
                    "--tool",
                    "ask",
                    "--arguments",
                    json.dumps({"question": "What is it?"}),
                    "--output",
                    directory,
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(server.calls[0]["name"], "ask")
        self.assertEqual(server.calls[0]["arguments"], {"question": "What is it?"})

    def test_a_fabricating_server_exits_nonzero(self) -> None:
        from beacon.cli import main

        server = self._server(answer=FABRICATED)
        with tempfile.TemporaryDirectory() as directory:
            code = main(
                [
                    "run",
                    str(SCENARIO),
                    "--adapter",
                    "mcp-tool",
                    "--mcp-url",
                    server.url,
                    "--tool",
                    "ask",
                    "--output",
                    directory,
                ]
            )
        self.assertEqual(code, 1)

    def test_the_cli_refuses_an_incomplete_invocation(self) -> None:
        from beacon.cli import main

        base = ["run", str(SCENARIO), "--adapter", "mcp-tool"]
        for label, extra in (
            ("no url", ["--tool", "ask"]),
            ("no tool", ["--mcp-url", "http://127.0.0.1:1/mcp"]),
            (
                "a command it cannot launch",
                ["--mcp-url", "http://127.0.0.1:1/mcp", "--tool", "ask",
                 "--command", "python3 x.py"],
            ),
            (
                "an environment option that would do nothing",
                ["--mcp-url", "http://127.0.0.1:1/mcp", "--tool", "ask",
                 "--env-secret", "TOKEN"],
            ),
        ):
            with self.subTest(case=label):
                with tempfile.TemporaryDirectory() as directory:
                    code = main(base + extra + ["--output", directory])
                self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
