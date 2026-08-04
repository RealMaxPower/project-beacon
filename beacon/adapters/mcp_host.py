from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Sequence

from beacon.adapters.base import ExecutionContext
from beacon.adapters.command import (
    DEFAULT_TEARDOWN_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    STDERR_TAIL_LINES,
    _safe_environment,
    resolve_command_paths,
)
from beacon.models import SubjectResult
from beacon.protocols.mcp_server import (
    SUBMIT_TOOL,
    MCPHTTPService,
    ScenarioMCPServer,
)


class MCPHostError(RuntimeError):
    """Raised when an MCP host subject cannot be run."""


def _write_config(path: Path, config: dict[str, Any]) -> None:
    """
    Write the client config so only this user can read it.

    The file carries the run's bearer token, and that token is the only thing
    between another local account and the scenario's tool facade — including
    `beacon_submit`, which decides the recorded verdict. `write_text` alone
    creates the file 0644 under the usual umask, and the redaction that
    protects evidence.json does not reach a sibling file.

    POSIX only, in effect: on Windows the mode is not expressible and the file
    is left to the ACLs it inherits from the run directory.
    """
    body = json.dumps(config, indent=2, ensure_ascii=False) + "\n"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(body)
    # O_CREAT leaves the mode alone on a file that already existed.
    os.chmod(path, 0o600)


class MCPHostAdapter:
    """
    Runs an MCP-speaking agent host against a scenario's tool surface.

    Two channels, which is the point. The MCP façade is the *tool* channel:
    the host connects and calls the scenario's synthetic tools, and Beacon
    records and grades every call exactly as it does over the JSONL bridge.
    This adapter is the *lifecycle* channel: it starts the façade, launches the
    host, and owns start, timeout, and termination.

    The façade alone could not produce a verdict. MCP gives no completion
    signal, so a clean disconnect and a crash are indistinguishable, and
    `subject_status` is the sole input to the result. Pairing the two recovers
    it — and the pairing is what the architecture doc means by a runtime
    adapter plus a scoped connection to Beacon's synthetic services.

    The host learns where to connect from a generated MCP config file and from
    BEACON_MCP_URL / BEACON_MCP_TOKEN in its environment. The bearer token is
    registered as a run secret, so it is redacted from the evidence bundle the
    same way an API key is.
    """

    def __init__(
        self,
        command: Sequence[str],
        *,
        name: str = "MCP host subject",
        timeout_seconds: float | None = None,
        teardown_seconds: float = DEFAULT_TEARDOWN_SECONDS,
        env_passthrough: Sequence[str] = (),
        env_secrets: Sequence[str] = (),
        server_name: str = "beacon",
        source_dir: str | Path | None = None,
    ) -> None:
        if not command:
            raise ValueError("command cannot be empty")
        self._command = tuple(command)
        self._source_dir = (
            Path(source_dir).resolve() if source_dir else Path.cwd().resolve()
        )
        self._name = name
        self._timeout_seconds = timeout_seconds
        self._teardown_seconds = teardown_seconds
        self._env_passthrough = tuple(env_passthrough)
        self._env_secrets = tuple(env_secrets)
        self._server_name = server_name

    @property
    def descriptor(self) -> dict[str, Any]:
        return {
            "id": "mcp-host",
            "name": self._name,
            "adapter": "mcp-host",
            "integration_level": 1,
            "command": list(self._command),
        }

    def _write_config(self, workspace: Path, url: str, token: str) -> Path:
        """
        Write an MCP client config the host can be pointed at.

        Shape follows the common `mcpServers` convention rather than any single
        product's schema — hosts differ, and a host that wants a different
        layout can read BEACON_MCP_URL and BEACON_MCP_TOKEN instead.
        """
        config = {
            "mcpServers": {
                self._server_name: {
                    "type": "http",
                    "url": url,
                    "headers": {"Authorization": f"Bearer {token}"},
                }
            }
        }
        path = workspace / "mcp-config.json"
        _write_config(path, config)
        return path

    def _resolve_command(self, **substitutions: str) -> tuple[str, ...]:
        substituted = tuple(token.format(**substitutions) for token in self._command)
        return resolve_command_paths(substituted, self._source_dir)

    def execute(self, context: ExecutionContext) -> SubjectResult:
        limits = context.scenario.limits
        timeout = float(
            self._timeout_seconds
            if self._timeout_seconds is not None
            else limits.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
        )
        for secret in self._env_secrets:
            value = os.environ.get(secret)
            if value is None:
                raise MCPHostError(
                    f"environment variable requested as a secret is not set: {secret}"
                )
            context.secrets.register(secret, value)

        server = ScenarioMCPServer(context.scenario, context.tools, context.recorder)
        service = MCPHTTPService(server)
        url = service.start()
        # The bearer token reaches the host's config file and environment, so
        # it is a secret like any other: register it before anything can echo
        # it back into the evidence bundle.
        context.secrets.register("BEACON_MCP_TOKEN", service.token)

        try:
            config_path = self._write_config(context.workspace, url, service.token)
            command = self._resolve_command(
                url=url,
                token=service.token,
                config=str(config_path),
                goal=context.scenario.goal,
                server=self._server_name,
            )
            environment = _safe_environment(
                context.run_id,
                self._env_passthrough,
                self._env_secrets,
            )
            environment.update(
                {
                    "BEACON_MCP_URL": url,
                    "BEACON_MCP_TOKEN": service.token,
                    "BEACON_MCP_CONFIG": str(config_path),
                    "BEACON_MCP_SERVER_NAME": self._server_name,
                    "BEACON_GOAL": context.scenario.goal,
                }
            )
            context.recorder.record(
                "subject_started",
                self.descriptor["id"],
                {
                    "command": list(command),
                    "mcp_url": url,
                    "timeout_seconds": timeout,
                    "tools": [item["name"] for item in server.tool_definitions()],
                    "env_passthrough": list(self._env_passthrough),
                    "env_secrets": list(self._env_secrets),
                },
            )
            result = self._run(context, server, command, environment, timeout)
        finally:
            service.stop()

        return result

    def _run(
        self,
        context: ExecutionContext,
        server: ScenarioMCPServer,
        command: tuple[str, ...],
        environment: dict[str, str],
        timeout: float,
    ) -> SubjectResult:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            cwd=context.workspace,
            env=environment,
        )
        timed_out = False
        try:
            _, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.terminate()
            try:
                _, stderr = process.communicate(timeout=self._teardown_seconds)
            except subprocess.TimeoutExpired:
                process.kill()
                _, stderr = process.communicate(timeout=self._teardown_seconds)

        stderr_tail = (stderr or "").splitlines()[-STDERR_TAIL_LINES:]
        exit_code = process.returncode
        submission = server.submission

        if submission and submission.get("artifact") is not None:
            artifact = context.scenario.required_artifact
            if artifact:
                context.add_artifact(artifact, submission["artifact"])

        context.recorder.record(
            "subject_completed",
            self.descriptor["id"],
            {
                "exit_code": exit_code,
                "timed_out": timed_out,
                "submitted": bool(submission),
                "client_info": server.client_info,
            },
        )

        if timed_out:
            return SubjectResult(
                status="timeout",
                error=f"host exceeded {timeout:g}s without submitting a result",
                metadata={"exit_code": exit_code, "stderr_tail": stderr_tail},
            )
        if submission is None:
            # The session ended and Beacon was never told the work finished.
            # That is not a statement about the subject's behavior, so it
            # resolves to INCOMPLETE rather than a failing verdict.
            return SubjectResult(
                status="no_submission",
                error=(
                    "host exited without calling beacon_submit, so Beacon "
                    "cannot tell whether the work was completed"
                ),
                metadata={"exit_code": exit_code, "stderr_tail": stderr_tail},
            )
        return SubjectResult(
            status=submission["status"],
            summary=submission["summary"],
            metadata={
                "exit_code": exit_code,
                "client_info": server.client_info,
                "stderr_tail": stderr_tail,
            },
        )


class MCPServeAdapter:
    """
    Serves the tool surface and waits for whoever connects.

    The same façade as `MCPHostAdapter`, without launching anything: point an
    agent host you already run — a desktop client, an IDE, another runtime — at
    the printed URL and watch it work against synthetic services.

    Nothing about the verdict is relaxed. Beacon still cannot see the host
    start, so it cannot distinguish "still thinking" from "gave up and closed
    the window". Only `beacon_submit` ends the wait with a verdict; a timeout
    or a Ctrl-C resolves INCOMPLETE, which is what Beacon actually knows.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float | None = None,
        poll_seconds: float = 0.25,
        announce: Any = print,
        server_name: str = "beacon",
        port: int = 0,
        token: str | None = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._poll_seconds = poll_seconds
        self._announce = announce
        self._server_name = server_name
        # A GUI host is configured by hand, and by default both the port and
        # the token change every run — so the config has to be re-pasted
        # before each one, which is enough friction to stop people trying.
        # Pinning them keeps one stored connector valid across runs.
        self._port = port
        self._token = token

    @property
    def descriptor(self) -> dict[str, Any]:
        return {
            "id": "mcp-serve",
            "name": "Externally connected MCP host",
            "adapter": "mcp-serve",
            "integration_level": 1,
        }

    def execute(self, context: ExecutionContext) -> SubjectResult:
        limits = context.scenario.limits
        timeout = float(
            self._timeout_seconds
            if self._timeout_seconds is not None
            else limits.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
        )
        server = ScenarioMCPServer(context.scenario, context.tools, context.recorder)
        service = MCPHTTPService(server, port=self._port, token=self._token)
        url = service.start()
        context.secrets.register("BEACON_MCP_TOKEN", service.token)

        config = {
            "mcpServers": {
                self._server_name: {
                    "type": "http",
                    "url": url,
                    "headers": {"Authorization": f"Bearer {service.token}"},
                }
            }
        }
        config_path = context.workspace / "mcp-config.json"
        _write_config(config_path, config)
        context.recorder.record(
            "subject_started",
            self.descriptor["id"],
            {
                "mcp_url": url,
                "timeout_seconds": timeout,
                "tools": [item["name"] for item in server.tool_definitions()],
            },
        )
        self._announce(
            f"MCP server: {url}\n"
            f"Config:     {config_path}\n"
            f"Goal:       {context.scenario.goal}\n\n"
            f"Connect an MCP host, then have it call {SUBMIT_TOOL} when done.\n"
            f"Waiting up to {timeout:g}s. Ctrl-C stops and still writes evidence."
        )

        interrupted = False
        deadline = time.monotonic() + timeout
        try:
            while server.submission is None and time.monotonic() < deadline:
                time.sleep(self._poll_seconds)
        except KeyboardInterrupt:
            interrupted = True
        finally:
            service.stop()

        submission = server.submission
        context.recorder.record(
            "subject_completed",
            self.descriptor["id"],
            {
                "submitted": bool(submission),
                "interrupted": interrupted,
                "client_info": server.client_info,
            },
        )
        if submission is None:
            return SubjectResult(
                status="interrupted" if interrupted else "no_submission",
                error=(
                    "stopped before a result was submitted"
                    if interrupted
                    else f"no host submitted a result within {timeout:g}s"
                ),
                metadata={"client_info": server.client_info},
            )
        artifact = context.scenario.required_artifact
        if artifact and submission.get("artifact") is not None:
            context.add_artifact(artifact, submission["artifact"])
        return SubjectResult(
            status=submission["status"],
            summary=submission["summary"],
            metadata={"client_info": server.client_info},
        )
