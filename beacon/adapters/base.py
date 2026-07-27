from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from beacon.models import EventRecorder, Scenario, SubjectResult
from beacon.secrets import SecretRegistry
from beacon.usage import UsageRecorder
from beacon.services.router import ToolRouter


@dataclass
class ExecutionContext:
    run_id: str
    run_dir: Path
    scenario: Scenario
    tools: ToolRouter
    recorder: EventRecorder
    artifacts: dict[str, Any] = field(default_factory=dict)
    secrets: SecretRegistry = field(default_factory=SecretRegistry)
    usage: UsageRecorder = field(default_factory=UsageRecorder)

    @property
    def workspace(self) -> Path:
        """
        Scratch space for the subject, kept out of the evidence directory.

        A subject given the evidence directory as its working directory can
        litter it, and with the default output location can reach the evidence
        of previous runs.
        """
        path = self.run_dir / "workspace"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def add_artifact(self, name: str, content: Any) -> None:
        self.artifacts[name] = content
        self.recorder.record(
            "artifact",
            name,
            {"content": content},
        )


class SubjectAdapter(Protocol):
    @property
    def descriptor(self) -> dict[str, Any]:
        """Describe the subject and integration level."""

    def execute(self, context: ExecutionContext) -> SubjectResult:
        """Run the subject against a prepared Beacon context."""

