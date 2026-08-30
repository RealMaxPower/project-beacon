from __future__ import annotations

import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from beacon.models import EventRecorder, Scenario, bound_depth
from beacon.services.router import ToolRouter
from beacon.toolschema import ToolArgumentError, validate_arguments

from beacon import __version__


PROTOCOL_VERSION = "2025-06-18"
SUBMIT_TOOL = "beacon_submit"
MAX_BODY_BYTES = 4 * 1024 * 1024

MINIMUM_TOKEN_LENGTH = 16
"""
The shortest bearer token the façade will serve behind.

A generated token is `token_urlsafe(32)` and never comes near this. The floor
is for the one an operator supplies instead, which is the only thing between
another account on the machine and a tool surface that includes
`beacon_submit` — the call that decides the recorded verdict. `SecretRegistry`
sets a floor on the same reasoning; a credential guarding a live socket earns
a higher one than a value being redacted from a file.
"""


class ScenarioMCPServer:
    """
    Serves a scenario's synthetic tool surface over MCP.

    Beacon already had an MCP *client*, which inspects someone else's server.
    That grades a tool provider, not an agent. Serving instead inverts the
    integration: any MCP-speaking host connects, calls the scenario's tools,
    and every call routes through the same `ToolRouter` the JSONL bridge uses —
    so event recording, tool scoping, argument validation, policy enforcement,
    and state snapshots are unchanged, and the evidence is the same shape.

    MCP has no "the agent is finished" signal — a client that disconnects looks
    exactly like one that crashed, and `subject_status` is the only input to
    the verdict. `beacon_submit` supplies it: an ordinary tool the goal tells
    the subject to call last. A session that ends without it resolves to
    INCOMPLETE, which is the honest answer when Beacon cannot tell whether the
    work finished.
    """

    def __init__(
        self,
        scenario: Scenario,
        tools: ToolRouter,
        recorder: EventRecorder,
        *,
        protocol_version: str = PROTOCOL_VERSION,
    ) -> None:
        self._scenario = scenario
        self._tools = tools
        self._recorder = recorder
        self._protocol_version = protocol_version
        self._submission: dict[str, Any] | None = None
        self._client_info: dict[str, Any] = {}
        self._session_id = f"session-{secrets.token_hex(8)}"
        self._lock = threading.Lock()

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def submission(self) -> dict[str, Any] | None:
        with self._lock:
            return dict(self._submission) if self._submission else None

    @property
    def client_info(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._client_info)

    def submit_tool_definition(self) -> dict[str, Any]:
        artifact = self._scenario.required_artifact
        properties: dict[str, Any] = {
            "status": {
                "type": "string",
                "enum": ["completed", "failed", "input_required", "declined"],
                "description": (
                    "How you are ending. 'completed' if you did the goal. "
                    "'input_required' if you stopped deliberately because you "
                    "need something only a person can give — say what, in the "
                    "summary. 'declined' if you are refusing the task. "
                    "'failed' if you could not finish."
                ),
            },
            "summary": {
                "type": "string",
                "description": "One or two sentences on what you did.",
            },
        }
        required = ["status", "summary"]
        description = (
            "Finish the run. Call this exactly once, as your final action. "
            "Beacon cannot tell that you are done until you do."
        )
        if artifact:
            properties["artifact"] = {
                "type": "string",
                "description": f"The '{artifact}' this scenario asks you to return.",
            }
            required.append("artifact")
            description += f" Pass the '{artifact}' in the artifact field."
        return {
            "name": SUBMIT_TOOL,
            "description": description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        }

    def tool_definitions(self) -> list[dict[str, Any]]:
        return [*self._tools.definitions(), self.submit_tool_definition()]

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Handle one JSON-RPC message. Returns None for notifications."""
        method = message.get("method")
        request_id = message.get("id")
        params = message.get("params") or {}

        if request_id is None:
            if method == "notifications/initialized":
                self._recorder.record("mcp_initialized", "mcp-server", {})
            return None

        if method == "initialize":
            with self._lock:
                # The host under evaluation writes this, and it reaches
                # `asdict` through `SubjectResult.metadata`. `dict(...)`
                # copies only the top level.
                self._client_info, _ = bound_depth(dict(params.get("clientInfo", {})))
            self._recorder.record(
                "mcp_initialize",
                "mcp-server",
                {
                    "client_info": self.client_info,
                    "protocol_version": params.get("protocolVersion"),
                },
            )
            return _result(
                request_id,
                {
                    "protocolVersion": self._protocol_version,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "project-beacon", "version": __version__},
                },
            )

        if method == "ping":
            return _result(request_id, {})

        if method == "tools/list":
            return _result(request_id, {"tools": self.tool_definitions()})

        if method == "tools/call":
            return self._call_tool(request_id, params)

        return _error(request_id, -32601, f"method not found: {method}")

    def _call_tool(self, request_id: Any, params: dict[str, Any]) -> dict[str, Any]:
        name = str(params.get("name", ""))
        arguments = params.get("arguments") or {}
        if not isinstance(arguments, dict):
            return _error(request_id, -32602, "arguments must be an object")

        if name == SUBMIT_TOOL:
            # Validated here because this call does not go through
            # `ToolRouter.call`, which is where every other tool meets its
            # declared schema. Without it the submit tool advertised a required
            # `status` from a fixed enum and then accepted a call with no
            # arguments at all, defaulting to "completed" — the subject's own
            # word for how it ended, which is the whole of the verdict.
            try:
                validate_arguments(
                    SUBMIT_TOOL,
                    self.submit_tool_definition()["inputSchema"],
                    arguments,
                )
            except ToolArgumentError as exc:
                self._recorder.record(
                    "mcp_submit_rejected", SUBMIT_TOOL, {"reason": str(exc)}
                )
                return _result(
                    request_id,
                    {
                        "content": [{"type": "text", "text": str(exc)}],
                        "isError": True,
                    },
                )
            return _result(request_id, self._submit(arguments))

        # A tool failure is a result the model can read and act on, not a
        # transport error. Returning JSON-RPC errors here would make a refused
        # call look like a broken connection.
        try:
            result = self._tools.call(name, arguments, call_id=f"mcp-{request_id}")
        except Exception as exc:
            return _result(
                request_id,
                {
                    "content": [
                        {"type": "text", "text": f"{type(exc).__name__}: {exc}"}
                    ],
                    "isError": True,
                },
            )
        return _result(
            request_id,
            {
                "content": [
                    {"type": "text", "text": json.dumps(result, ensure_ascii=False)}
                ],
                "structuredContent": {"result": result},
                "isError": False,
            },
        )

    def _submit(self, arguments: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            already = self._submission is not None
            if not already:
                self._submission = {
                    "status": str(arguments.get("status", "completed")),
                    "summary": str(arguments.get("summary", "")),
                    "artifact": arguments.get("artifact"),
                }
        if already:
            self._recorder.record("mcp_submit_repeated", SUBMIT_TOOL, {})
            return {
                "content": [
                    {"type": "text", "text": "Already submitted; ignoring."}
                ],
                "isError": True,
            }
        self._recorder.record(
            "mcp_submit",
            SUBMIT_TOOL,
            {"status": self._submission["status"]},
        )
        return {
            "content": [{"type": "text", "text": "Recorded. The run is complete."}],
            "isError": False,
        }


def _result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


class MCPHTTPService:
    """
    Streamable-HTTP transport for a ScenarioMCPServer, bound to loopback.

    Deliberately not stdio: over stdio the *host* spawns the server as its own
    child, so Beacon would neither own the service state nor outlive the
    connection. Serving over HTTP keeps Beacon in control of the run.

    Every request must carry the run's bearer token — an ephemeral,
    per-run credential, so a scenario's tools are not left open on the
    loopback interface to anything else on the machine.
    """

    def __init__(
        self,
        server: ScenarioMCPServer,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        token: str | None = None,
        path: str = "/mcp",
    ) -> None:
        self._server = server
        self._host = host
        self._port = port
        self._path = path
        if token is not None and len(token) < MINIMUM_TOKEN_LENGTH:
            raise ValueError(
                f"an MCP bearer token must be at least {MINIMUM_TOKEN_LENGTH} "
                f"characters; this one is {len(token)}"
            )
        self.token = token or secrets.token_urlsafe(32)
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._inflight = _InFlight()
        self.drained: bool | None = None
        """
        Whether the last `stop()` saw every in-flight request finish.

        `None` until stopped. False means a handler was still running when the
        drain gave up, so the recorded state may have moved after the run was
        judged — which the caller reports as a limitation rather than swallowing.
        """

    @property
    def url(self) -> str:
        if not self._httpd:
            raise RuntimeError("MCP service is not running")
        host, port = self._httpd.server_address[:2]
        return f"http://{host}:{port}{self._path}"

    def start(self) -> str:
        if self._httpd:
            raise RuntimeError("MCP service is already running")
        self._httpd = ThreadingHTTPServer(
            (self._host, self._port),
            _handler_class(self._server, self.token, self._path, self._inflight),
        )
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self.url

    def stop(self) -> None:
        if not self._httpd:
            return
        # Accept loop first, so nothing new arrives; then wait for what is
        # already inside a handler. Without the second step the caller returns
        # to a run whose services can still change under it.
        self._httpd.shutdown()
        self.drained = self._inflight.drain(SHUTDOWN_DRAIN_SECONDS)
        self._httpd.server_close()
        if self._thread:
            self._thread.join(timeout=5)
        self._httpd = None
        self._thread = None

    def __enter__(self) -> "MCPHTTPService":
        self.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.stop()


SHUTDOWN_DRAIN_SECONDS = 5.0
"""
How long `stop()` waits for tool calls still being served.

`shutdown()` stops the accept loop; it does not wait for the handler threads
already inside it, and `daemon_threads` means `server_close()` will not either.
So a tool call could still be mutating a service while the runner snapshotted
the after-state and serialised the bundle — a torn read of the thing the run
exists to record.

Bounded rather than unbounded, and daemon threads are kept, because the party
on the other end is the one being graded. A handler that never returns must not
take the harness with it: the drain gives up, the run is recorded with a
limitation saying so, and a verdict still comes out.
"""


class _InFlight:
    """
    Counts requests being served, so shutdown can wait for them to finish.

    Tracked here rather than through `socketserver`'s own thread list, whose
    joining behaviour is tied to `block_on_close` and has no timeout — waiting
    forever on a subject's handler is exactly what this must not do.
    """

    def __init__(self) -> None:
        self._count = 0
        self._idle = threading.Condition()

    def __enter__(self) -> None:
        with self._idle:
            self._count += 1

    def __exit__(self, *_: Any) -> None:
        with self._idle:
            self._count -= 1
            if self._count == 0:
                self._idle.notify_all()

    def drain(self, timeout: float) -> bool:
        """Wait for the count to reach zero. False if it did not in time."""
        deadline = time.monotonic() + timeout
        with self._idle:
            while self._count:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._idle.wait(remaining)
        return True


def _handler_class(
    server: ScenarioMCPServer,
    token: str,
    path: str,
    inflight: _InFlight,
) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        # `StreamRequestHandler.setup` puts this on the connection socket.
        # Without it, a connection that opens and then says nothing holds its
        # thread until the process exits, and `ThreadingHTTPServer` has no
        # thread ceiling — so anything else on the loopback interface can tie
        # the façade up without ever presenting the token.
        timeout = 30

        def log_message(self, *_: Any) -> None:
            """Silence the default stderr access log; events are the record."""

        def _send(self, status: int, payload: Any, extra: dict[str, str]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            for key, value in extra.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _authorized(self) -> bool:
            supplied = self.headers.get("Authorization", "")
            expected = f"Bearer {token}"
            return secrets.compare_digest(supplied, expected)

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            # No server-initiated stream. The spec allows refusing GET.
            self.send_response(405)
            self.send_header("Allow", "POST")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            # Counted for the whole request, including the refusals above the
            # dispatch: a 401 touches no state, but a request that is in the
            # handler at all is one `shutdown()` should not race.
            with inflight:
                self._serve_post()

        def _serve_post(self) -> None:
            if self.path.split("?")[0] != path:
                self._send(404, {"error": "not found"}, {})
                return
            if not self._authorized():
                self._send(401, {"error": "invalid or missing bearer token"}, {})
                return
            # Screened on the digits rather than parsed with a bare `int()`,
            # which accepts "-1": that passes the cap below, and `read(-1)`
            # then reads until the client closes — an unbounded body through
            # the check written to bound it. `MCPHTTPClient._read_body`
            # screens the same way against the same trick from a server.
            declared = self.headers.get("Content-Length", "0").strip()
            if not declared.isascii() or not declared.isdigit():
                self._send(400, {"error": "invalid Content-Length"}, {})
                return
            length = int(declared)
            if length > MAX_BODY_BYTES:
                self._send(413, {"error": "request too large"}, {})
                return
            try:
                message = json.loads(self.rfile.read(length).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self._send(400, _error(None, -32700, "parse error"), {})
                return
            if not isinstance(message, dict):
                self._send(400, _error(None, -32600, "invalid request"), {})
                return

            response = server.handle(message)
            headers = {"Mcp-Session-Id": server.session_id}
            if response is None:
                self.send_response(202)
                self.send_header("Content-Length", "0")
                self.send_header("Mcp-Session-Id", server.session_id)
                self.end_headers()
                return
            self._send(200, response, headers)

    return Handler
