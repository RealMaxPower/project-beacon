from __future__ import annotations

from typing import Any

from beacon.adapters.base import ExecutionContext
from beacon.models import SubjectResult


class ReferenceInboxAdapter:
    """Deterministic reference subject for exercising the Beacon core."""

    @property
    def descriptor(self) -> dict[str, Any]:
        return {
            "id": "reference-inbox-agent",
            "name": "Beacon reference inbox agent",
            "adapter": "in-process",
            "integration_level": 4,
            "version": "0.1.0",
        }

    def execute(self, context: ExecutionContext) -> SubjectResult:
        context.recorder.record(
            "subject_started",
            self.descriptor["id"],
            {"goal": context.scenario.goal},
        )
        messages = context.tools.call("mail.list_messages", {}, call_id="ref-001")
        action_messages = [
            message
            for message in messages
            if "action_required" in message.get("labels", [])
        ]

        summary_lines: list[str] = []
        for index, message_header in enumerate(action_messages, start=1):
            message = context.tools.call(
                "mail.read_message",
                {"message_id": message_header["id"]},
                call_id=f"ref-read-{index:03d}",
            )
            summary_lines.append(
                f"- [{message['id']}] {message['subject']} — {message['body']}"
            )
            context.tools.call(
                "mail.create_draft",
                {
                    "to": message["sender"],
                    "subject": f"Re: {message['subject']}",
                    "body": (
                        "Thanks for the note. I reviewed it and will confirm the "
                        "requested next step after a human review."
                    ),
                    "in_reply_to": message["id"],
                },
                call_id=f"ref-draft-{index:03d}",
            )

        summary = "Action-required inbox briefing\n\n" + "\n".join(summary_lines)
        context.add_artifact("summary", summary)
        context.recorder.record(
            "subject_completed",
            self.descriptor["id"],
            {"action_messages": len(action_messages)},
        )
        return SubjectResult(
            status="completed",
            summary=f"Prepared {len(action_messages)} draft responses.",
            metadata={"action_messages": len(action_messages)},
        )

