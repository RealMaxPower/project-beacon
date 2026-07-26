from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from beacon.models import EventRecorder, Scenario, SubjectResult
from beacon.services.router import ToolRouter


@dataclass
class ExecutionContext:
    run_id: str
    run_dir: Path
    scenario: Scenario
    tools: ToolRouter
    recorder: EventRecorder
    artifacts: dict[str, Any] = field(default_factory=dict)

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

