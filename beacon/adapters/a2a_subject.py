from __future__ import annotations

from typing import Any

from beacon.adapters.base import ExecutionContext
from beacon.models import SubjectResult
from beacon.protocols.a2a import A2AClient, A2AError
from beacon.usage import UsageLimitExceeded


TERMINAL_OK = {"completed", "TASK_STATE_COMPLETED"}
TERMINAL_BAD = {
    "failed",
    "canceled",
    "cancelled",
    "rejected",
    "TASK_STATE_FAILED",
    "TASK_STATE_CANCELED",
}
NEEDS_MORE = {"auth-required", "input-required", "TASK_STATE_INPUT_REQUIRED"}


class A2ASubjectAdapter:
    """
    Grades a hosted A2A agent on what it returns.

    This is a different shape of evidence from the other adapters, and the
    difference is worth being explicit about. A JSONL or MCP subject calls
    Beacon's synthetic services, so Beacon can diff the state it left behind.
    An A2A service agent calls its *own* tools against the real world and hands
    back artifacts — Beacon's mail store never moves. There is no state to
    diff, so the evidence is the response: what the agent claimed, whether the
    claims are grounded in the source it was given, how long it took, and
    whether it did anything it was told not to.

    That is Level 0/2 in the compatibility table, and it is the honest ceiling
    for an agent that does not accept a tool surface from the harness.
    """

    def __init__(
        self,
        base_url: str,
        *,
        name: str | None = None,
        timeout_seconds: float | None = None,
        authorization: str | None = None,
        artifact_name: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._name = name or base_url
        self._timeout_seconds = timeout_seconds
        self._authorization = authorization
        self._artifact_name = artifact_name

    @property
    def descriptor(self) -> dict[str, Any]:
        return {
            "id": "a2a",
            "name": self._name,
            "adapter": "a2a",
            "integration_level": 2,
            "agent_url": self._base_url,
        }

    def _store_artifacts(
        self,
        context: ExecutionContext,
        result: dict[str, Any],
    ) -> list[str]:
        """
        Record what the agent returned, under names a scenario can assert on.

        A2A artifacts carry typed parts; both text and structured `data` parts
        are kept as-is so an assertion can search either without the adapter
        having to guess which one matters.
        """
        stored: list[str] = []
        artifacts = result.get("artifacts") or []
        for index, artifact in enumerate(artifacts):
            parts = artifact.get("parts") or []
            payload: Any
            values = [
                part.get("data") if "data" in part else part.get("text")
                for part in parts
            ]
            values = [value for value in values if value is not None]
            payload = values[0] if len(values) == 1 else values
            name = self._artifact_name or artifact.get("name") or f"artifact-{index}"
            context.add_artifact(name, payload)
            stored.append(name)

        # A task can answer in messages rather than artifacts.
        for message in result.get("history") or []:
            if message.get("role") != "agent":
                continue
            text = "".join(
                part.get("text", "") for part in message.get("parts") or []
            )
            if text:
                context.add_artifact("agent_message", text)
                stored.append("agent_message")
                break
        return stored

    def execute(self, context: ExecutionContext) -> SubjectResult:
        limits = context.scenario.limits
        timeout = float(
            self._timeout_seconds
            if self._timeout_seconds is not None
            else limits.get("timeout_seconds", 120)
        )
        client = A2AClient(
            self._base_url,
            timeout_seconds=timeout,
            authorization=self._authorization,
        )

        try:
            with context.usage.timed("a2a_discover", self._base_url) as timer:
                card = client.discover()
        except (A2AError, UsageLimitExceeded) as exc:
            context.recorder.record(
                "subject_error", "a2a", {"stage": "discover", "message": str(exc)}
            )
            return SubjectResult(status="error", error=f"discovery failed: {exc}")

        context.recorder.record(
            "a2a_agent_card",
            self._base_url,
            {
                "name": card.get("name"),
                "version": card.get("version"),
                "protocol_version": card.get("protocolVersion"),
                "capabilities": card.get("capabilities", {}),
                "skills": [s.get("id") for s in card.get("skills") or []],
                "security_schemes": sorted(card.get("securitySchemes") or {}),
            },
        )

        try:
            with context.usage.timed("a2a_message", self._base_url) as timer:
                response = client.send_message(context.scenario.goal)
                timer.detail["goal_chars"] = len(context.scenario.goal)
        except UsageLimitExceeded as exc:
            context.recorder.record("usage_limit", "a2a", {"message": str(exc)})
            return SubjectResult(status="budget_exceeded", error=str(exc))
        except A2AError as exc:
            context.recorder.record(
                "subject_error", "a2a", {"stage": "message", "message": str(exc)}
            )
            return SubjectResult(status="error", error=str(exc))

        result = response.get("result") or response.get("task") or {}
        state = str((result.get("status") or {}).get("state", "unknown"))
        stored = self._store_artifacts(context, result)

        context.recorder.record(
            "a2a_task",
            self._base_url,
            {
                "task_id": result.get("id") or result.get("taskId"),
                "state": state,
                "artifacts": stored,
                "elapsed_seconds": round(context.usage.total_seconds, 3),
            },
        )

        if state in NEEDS_MORE:
            # The agent answered correctly; it just cannot proceed without
            # something Beacon did not supply. That is not a failing verdict.
            return SubjectResult(
                status="input_required",
                error=f"agent returned state {state!r} and cannot proceed",
                metadata={"state": state, "artifacts": stored},
            )
        if state in TERMINAL_BAD:
            return SubjectResult(
                status="agent_failed",
                error=f"agent finished in state {state!r}",
                metadata={"state": state, "artifacts": stored},
            )
        if state not in TERMINAL_OK:
            return SubjectResult(
                status="unknown_state",
                error=f"agent returned an unrecognized task state: {state!r}",
                metadata={"state": state, "artifacts": stored},
            )
        return SubjectResult(
            status="completed",
            summary=f"Returned {len(stored)} artifact(s) in state {state}.",
            metadata={
                "state": state,
                "artifacts": stored,
                "agent_name": card.get("name"),
                "agent_version": card.get("version"),
            },
        )
