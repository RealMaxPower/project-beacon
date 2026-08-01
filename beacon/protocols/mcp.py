from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from typing import Any, Sequence, TextIO


class MCPError(RuntimeError):
    """Raised when an MCP server cannot complete a protocol operation."""


def _read_lines(stream: TextIO, output: queue.Queue[str | None]) -> None:
    try:
        for line in stream:
            output.put(line)
    finally:
        output.put(None)


def _mcp_environment() -> dict[str, str]:
    allowed = (
        "PATH",
        "LANG",
        "LC_ALL",
        "SYSTEMROOT",
        "WINDIR",
        "TMPDIR",
        "TEMP",
        "TMP",
        "NODE_PATH",
    )
    return {key: os.environ[key] for key in allowed if key in os.environ}


class MCPStdioClient:
    """
    Minimal MCP stdio client for protocol inspection and deterministic calls.

    The client intentionally implements a narrow stable surface: initialize,
    tools/list, and tools/call. It uses newline-delimited JSON-RPC messages.
    """

    def __init__(
        self,
        command: Sequence[str],
        *,
        timeout_seconds: float = 10,
        protocol_version: str = "2025-06-18",
    ) -> None:
        if not command:
            raise ValueError("MCP command cannot be empty")
        self.command = tuple(command)
        self.timeout_seconds = timeout_seconds
        self.protocol_version = protocol_version
        self._process: subprocess.Popen[str] | None = None
        self._stdout_queue: queue.Queue[str | None] = queue.Queue()
        self._stderr_queue: queue.Queue[str | None] = queue.Queue()
        self._request_id = 0
        self.server_info: dict[str, Any] = {}
        self.capabilities: dict[str, Any] = {}

    def __enter__(self) -> "MCPStdioClient":
        self.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def start(self) -> None:
        if self._process:
            raise MCPError("MCP client already started")
        process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=_mcp_environment(),
        )
        if not process.stdin or not process.stdout or not process.stderr:
            process.kill()
            process.wait(timeout=2)
            raise MCPError("failed to open MCP stdio streams")
        self._process = process
        threading.Thread(
            target=_read_lines,
            args=(process.stdout, self._stdout_queue),
            daemon=True,
        ).start()
        threading.Thread(
            target=_read_lines,
            args=(process.stderr, self._stderr_queue),
            daemon=True,
        ).start()

        # Everything past this point can fail on the server's behaviour rather
        # than ours - unparseable output, a missing protocolVersion, a hang -
        # and a start() that raises with the child still running leaks the
        # process and its three pipes. The caller has no handle to close,
        # because it never got one.
        try:
            response = self.request(
                "initialize",
                {
                    "protocolVersion": self.protocol_version,
                    "capabilities": {},
                    "clientInfo": {
                        "name": "project-beacon",
                        "version": "0.1.0",
                    },
                },
            )
            negotiated = response.get("protocolVersion")
            if not negotiated:
                raise MCPError("MCP initialize response omitted protocolVersion")
            self.protocol_version = str(negotiated)
            self.server_info = dict(response.get("serverInfo", {}))
            self.capabilities = dict(response.get("capabilities", {}))
            self.notify("notifications/initialized")
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        process = self._process
        self._process = None
        if not process:
            return
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        if process.stdout and not process.stdout.closed:
            process.stdout.close()
        if process.stderr and not process.stderr.closed:
            process.stderr.close()

    def _send(self, value: dict[str, Any]) -> None:
        if not self._process or not self._process.stdin:
            raise MCPError("MCP client is not started")
        self._process.stdin.write(
            json.dumps(value, separators=(",", ":"), ensure_ascii=False) + "\n"
        )
        self._process.stdin.flush()

    def _stderr(self) -> str:
        lines: list[str] = []
        while True:
            try:
                line = self._stderr_queue.get_nowait()
            except queue.Empty:
                break
            if line is None:
                break
            lines.append(line.rstrip())
        return "\n".join(lines)

    def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._request_id += 1
        request_id = self._request_id
        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params
        self._send(message)
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MCPError(f"MCP request timed out: {method}")
            try:
                line = self._stdout_queue.get(timeout=min(remaining, 0.25))
            except queue.Empty:
                if self._process and self._process.poll() is not None:
                    raise MCPError(
                        f"MCP server exited with code {self._process.returncode}: "
                        f"{self._stderr()}"
                    )
                continue
            if line is None:
                raise MCPError(f"MCP server closed stdout: {self._stderr()}")
            if not line.strip():
                # Blank lines are legal framing in a newline-delimited stream
                # and real servers emit them, especially while a launcher is
                # still installing. Treating one as a protocol violation turned
                # an intermittent hiccup into a failed run.
                continue
            try:
                response = json.loads(line)
            except json.JSONDecodeError as exc:
                # Without the server's stderr this reads as "invalid JSON: "
                # and says nothing about what went wrong.
                raise MCPError(
                    f"MCP server emitted invalid JSON on {method}: "
                    f"{line.strip()[:200]!r}. Server stderr: {self._stderr()[:400]!r}"
                ) from exc
            if response.get("id") != request_id:
                continue
            if "error" in response:
                raise MCPError(f"MCP error for {method}: {response['error']}")
            if "result" not in response:
                raise MCPError(f"MCP response for {method} omitted result")
            return response["result"]

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            message["params"] = params
        self._send(message)

    def list_tools(self) -> list[dict[str, Any]]:
        result = self.request("tools/list", {})
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            raise MCPError("tools/list result must contain a tools array")
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self.request(
            "tools/call",
            {
                "name": name,
                "arguments": arguments,
            },
        )
        if not isinstance(result, dict):
            raise MCPError("tools/call result must be an object")
        return result
