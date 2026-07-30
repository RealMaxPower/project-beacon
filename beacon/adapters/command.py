from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Sequence, TextIO

from beacon.adapters.base import ExecutionContext
from beacon.models import SubjectResult


class CommandAdapterError(RuntimeError):
    """Raised when a JSONL command subject violates the adapter contract."""


DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_PROTOCOL_MESSAGES = 500
DEFAULT_TEARDOWN_SECONDS = 10.0
STDERR_TAIL_LINES = 20


def _reader(stream: TextIO, output: queue.Queue[str | None]) -> None:
    try:
        for line in stream:
            output.put(line)
    finally:
        output.put(None)


def _safe_environment(
    run_id: str,
    passthrough: Sequence[str] = (),
    secrets: Sequence[str] = (),
) -> dict[str, str]:
    """
    Build the subject's environment: deny by default, with named exceptions.

    The allowlist alone makes a credentialed agent impossible to run, since it
    carries no HOME and no API key. `passthrough` and `secrets` are explicit
    operator escapes from that, not a relaxation of it: only the names asked
    for are copied, and only from Beacon's own environment.
    """
    allowed = (
        "PATH",
        "LANG",
        "LC_ALL",
        "SYSTEMROOT",
        "WINDIR",
        "TMPDIR",
        "TEMP",
        "TMP",
    )
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    for name in (*passthrough, *secrets):
        if name in os.environ:
            environment[name] = os.environ[name]
    environment["BEACON_RUN_ID"] = run_id
    environment["PYTHONUNBUFFERED"] = "1"
    # Pipes default to the locale encoding, which on Windows is not UTF-8. The
    # adapter reads and writes UTF-8, so without this a subject emitting any
    # non-ASCII character produces a decode error rather than a verdict.
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def resolve_command_paths(
    command: Sequence[str],
    source_dir: Path,
) -> tuple[str, ...]:
    """
    Make relative paths in a command absolute, against the invocation directory.

    Subjects run in `<run>/workspace/`, not where the user typed the command,
    so `python3 examples/agent.py` would otherwise resolve against the wrong
    directory and fail with a file-not-found naming a path nobody wrote.
    """
    resolved: list[str] = []
    for token in command:
        candidate = source_dir / token
        if (
            not token.startswith("-")
            and not Path(token).is_absolute()
            and candidate.exists()
        ):
            resolved.append(str(candidate.resolve()))
        else:
            resolved.append(token)
    return tuple(resolved)


def _drain(output: queue.Queue[str | None]) -> list[str]:
    lines: list[str] = []
    while True:
        try:
            item = output.get_nowait()
        except queue.Empty:
            break
        if item is None:
            break
        lines.append(item.rstrip())
    return lines


def _close_process_streams(process: subprocess.Popen[str]) -> None:
    for stream in (process.stdin, process.stdout, process.stderr):
        if stream and not stream.closed:
            stream.close()


class JSONLCommandAdapter:
    """
    A small bidirectional JSONL bridge for wrapping CLI, API, or SDK agents.

    This is an interoperability harness, not a hardened sandbox.
    """

    def __init__(
        self,
        command: Sequence[str],
        *,
        name: str = "JSONL command subject",
        timeout_seconds: float | None = None,
        max_messages: int | None = None,
        teardown_seconds: float = DEFAULT_TEARDOWN_SECONDS,
        env_passthrough: Sequence[str] = (),
        env_secrets: Sequence[str] = (),
        source_dir: str | Path | None = None,
    ) -> None:
        if not command:
            raise ValueError("command cannot be empty")
        self._command = tuple(command)
        self._name = name
        self._timeout_seconds = timeout_seconds
        self._max_messages = max_messages
        self._teardown_seconds = teardown_seconds
        self._env_passthrough = tuple(env_passthrough)
        self._env_secrets = tuple(env_secrets)
        self._source_dir = (
            Path(source_dir).resolve() if source_dir else Path.cwd().resolve()
        )

    def _limits(self, context: ExecutionContext) -> tuple[float, int]:
        """
        Resolve the run's budgets, preferring the scenario's declared limits.

        Constructor arguments are explicit operator overrides, so when one
        differs from what the scenario declared the difference is recorded.
        A scenario that publishes a limit into its evidence and then runs under
        a different one is misleading about the conditions of the run.
        """
        declared = context.scenario.limits
        timeout = float(declared.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
        messages = int(
            declared.get("max_protocol_messages", DEFAULT_MAX_PROTOCOL_MESSAGES)
        )
        overrides: dict[str, Any] = {}
        if self._timeout_seconds is not None and self._timeout_seconds != timeout:
            overrides["timeout_seconds"] = {
                "declared": timeout,
                "applied": self._timeout_seconds,
            }
            timeout = self._timeout_seconds
        if self._max_messages is not None and self._max_messages != messages:
            overrides["max_protocol_messages"] = {
                "declared": messages,
                "applied": self._max_messages,
            }
            messages = self._max_messages
        if overrides:
            context.recorder.record(
                "limits_overridden",
                self.descriptor["id"],
                overrides,
            )
        return timeout, messages

    def _resolved_command(self) -> tuple[str, ...]:
        return resolve_command_paths(self._command, self._source_dir)

    @property
    def descriptor(self) -> dict[str, Any]:
        return {
            "id": "jsonl-command",
            "name": self._name,
            "adapter": "jsonl-command",
            "integration_level": 3,
            "command": list(self._command),
        }

    def _send(self, stream: TextIO, value: dict[str, Any]) -> None:
        stream.write(json.dumps(value, separators=(",", ":")) + "\n")
        stream.flush()

    def _register_secrets(self, context: ExecutionContext) -> list[str]:
        """Teach the run's registry every secret value before it can leak."""
        missing: list[str] = []
        for name in self._env_secrets:
            value = os.environ.get(name)
            if value is None:
                missing.append(name)
                continue
            context.secrets.register(name, value)
        return missing

    def execute(self, context: ExecutionContext) -> SubjectResult:
        resolved_command = self._resolved_command()
        timeout_seconds, max_messages = self._limits(context)
        missing_secrets = self._register_secrets(context)
        if missing_secrets:
            raise CommandAdapterError(
                "environment variable(s) requested as secrets are not set: "
                + ", ".join(missing_secrets)
            )
        context.recorder.record(
            "subject_started",
            self.descriptor["id"],
            {
                "command": list(resolved_command),
                "timeout_seconds": timeout_seconds,
                "max_protocol_messages": max_messages,
                "env_passthrough": list(self._env_passthrough),
                # Names only. The values are registered for redaction, never
                # recorded - this payload lands in evidence.json.
                "env_secrets": list(self._env_secrets),
            },
        )
        process = subprocess.Popen(
            resolved_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            cwd=context.workspace,
            env=_safe_environment(
                context.run_id,
                self._env_passthrough,
                self._env_secrets,
            ),
        )
        if not process.stdin or not process.stdout or not process.stderr:
            process.kill()
            raise CommandAdapterError("failed to open command protocol streams")

        stdout_queue: queue.Queue[str | None] = queue.Queue()
        stderr_queue: queue.Queue[str | None] = queue.Queue()
        threading.Thread(
            target=_reader,
            args=(process.stdout, stdout_queue),
            daemon=True,
        ).start()
        threading.Thread(
            target=_reader,
            args=(process.stderr, stderr_queue),
            daemon=True,
        ).start()

        self._send(
            process.stdin,
            {
                "type": "start",
                "protocol_version": "0.1",
                "run_id": context.run_id,
                "scenario": context.scenario.public_dict(),
                "tools": context.tools.definitions(),
            },
        )

        deadline = time.monotonic() + timeout_seconds
        handled = 0
        result: SubjectResult | None = None
        try:
            while result is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise CommandAdapterError(
                        f"subject exceeded {timeout_seconds:g}s timeout"
                    )
                try:
                    line = stdout_queue.get(timeout=min(remaining, 0.25))
                except queue.Empty:
                    if process.poll() is not None:
                        raise CommandAdapterError(
                            f"subject exited before completion with code {process.returncode}"
                        )
                    continue
                if line is None:
                    raise CommandAdapterError("subject closed stdout before completion")
                handled += 1
                if handled > max_messages:
                    raise CommandAdapterError(
                        f"subject exceeded {max_messages} protocol messages"
                    )
                try:
                    message = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise CommandAdapterError(
                        f"subject emitted invalid JSONL: {line.strip()}"
                    ) from exc
                message_type = message.get("type")

                if message_type == "tool_call":
                    call_id = str(message.get("id", f"call-{handled:03d}"))
                    tool = str(message.get("tool", ""))
                    arguments = message.get("arguments", {})
                    if not isinstance(arguments, dict):
                        raise CommandAdapterError("tool_call arguments must be an object")
                    try:
                        tool_result = context.tools.call(
                            tool,
                            arguments,
                            call_id=call_id,
                        )
                    except Exception as exc:
                        self._send(
                            process.stdin,
                            {
                                "type": "tool_result",
                                "id": call_id,
                                "ok": False,
                                "error": {
                                    "type": type(exc).__name__,
                                    "message": str(exc),
                                },
                            },
                        )
                    else:
                        self._send(
                            process.stdin,
                            {
                                "type": "tool_result",
                                "id": call_id,
                                "ok": True,
                                "result": tool_result,
                            },
                        )
                    continue

                if message_type == "artifact":
                    name = str(message.get("name", "artifact"))
                    context.add_artifact(name, message.get("content"))
                    continue

                if message_type == "log":
                    context.recorder.record(
                        "subject_log",
                        self.descriptor["id"],
                        {
                            "level": message.get("level", "info"),
                            "message": message.get("message", ""),
                        },
                    )
                    continue

                if message_type == "complete":
                    status = str(message.get("status", "completed"))
                    result = SubjectResult(
                        status=status,
                        summary=str(message.get("summary", "")),
                        metadata=dict(message.get("metadata", {})),
                        error=message.get("error"),
                    )
                    continue

                raise CommandAdapterError(
                    f"unsupported command message type: {message_type!r}"
                )
        except CommandAdapterError as exc:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
            # The subject's stderr is the only thing that explains why it
            # stopped, and until now it was drained solely on the success
            # path — so a crashed subject reported "closed stdout before
            # completion" and threw away the traceback that said what
            # happened. Anyone debugging got the symptom and nothing else.
            tail = _drain(stderr_queue)[-STDERR_TAIL_LINES:]
            _close_process_streams(process)
            if tail:
                raise CommandAdapterError(
                    f"{exc}\nsubject stderr:\n  " + "\n  ".join(tail)
                ) from exc
            raise
        except Exception:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
            _close_process_streams(process)
            raise
        finally:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()

        # The subject has already reported `complete`; the protocol work is
        # done. What follows is teardown, and nothing it reveals can retract a
        # completion that was validly sent. Closing an HTTP pool, joining a
        # thread, or a failing atexit handler are all normal, and treating them
        # as subject errors reports INCOMPLETE for work that finished.
        terminated = False
        try:
            return_code = process.wait(timeout=self._teardown_seconds)
        except subprocess.TimeoutExpired:
            terminated = True
            process.terminate()
            try:
                return_code = process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                return_code = process.wait(timeout=2)

        stderr_tail = _drain(stderr_queue)[-STDERR_TAIL_LINES:]
        _close_process_streams(process)

        if terminated or return_code != 0:
            context.recorder.record(
                "subject_teardown",
                self.descriptor["id"],
                {
                    "exit_code": return_code,
                    "terminated_after_complete": terminated,
                    "teardown_seconds": self._teardown_seconds,
                    "stderr_tail": stderr_tail,
                },
            )

        result.metadata = {
            **result.metadata,
            "exit_code": return_code,
            "terminated_after_complete": terminated,
        }
        context.recorder.record(
            "subject_completed",
            self.descriptor["id"],
            {"status": result.status, "exit_code": return_code},
        )
        return result
