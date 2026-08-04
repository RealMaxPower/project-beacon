from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from beacon.models import EventRecorder, Scenario, SubjectResult, bound_depth
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
    # Things the harness had to do to the subject's own output, which the
    # bundle has to admit to rather than quietly present as what was sent.
    limitations: list[str] = field(default_factory=list)

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
        """
        Record an artifact the subject produced.

        The content is whatever the subject sent, so its nesting is the
        subject's choice. It is bounded here, at the door, because past this
        point it is walked by `asdict` and by the JSON encoder, and a
        `RecursionError` in either loses the whole bundle for a run the
        subject has already been paid for.
        """
        content, truncated = bound_depth(content)
        payload: dict[str, Any] = {"content": content}
        if truncated:
            # Only when it happened: an event shape that changes for every
            # ordinary run would churn every recorded fixture.
            payload["depth_truncated"] = True
            self.limitations.append(
                f"The artifact {name!r} was nested too deeply to record in "
                f"full, so the deepest levels were replaced with a marker."
            )
        self.artifacts[name] = content
        self.recorder.record("artifact", name, payload)


class SubjectAdapter(Protocol):
    @property
    def descriptor(self) -> dict[str, Any]:
        """Describe the subject and integration level."""

    def execute(self, context: ExecutionContext) -> SubjectResult:
        """Run the subject against a prepared Beacon context."""

