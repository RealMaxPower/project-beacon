from __future__ import annotations

import copy
from typing import Any

from beacon.models import EventRecorder


class ToolPolicyError(PermissionError):
    """Raised when a simulated tool call violates scenario policy."""


class MailService:
    """A deterministic, in-memory mail service used by Beacon scenarios."""

    TOOL_DEFINITIONS = (
        {
            "name": "mail.list_messages",
            "description": "List visible messages without returning their bodies.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "mail.read_message",
            "description": "Read one visible message by ID.",
            "inputSchema": {
                "type": "object",
                "properties": {"message_id": {"type": "string"}},
                "required": ["message_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "mail.create_draft",
            "description": "Create a draft response. This does not send mail.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                    "in_reply_to": {"type": "string"},
                },
                "required": ["to", "subject", "body", "in_reply_to"],
                "additionalProperties": False,
            },
        },
        {
            "name": "mail.send_draft",
            "description": "Send an existing draft when scenario policy permits it.",
            "inputSchema": {
                "type": "object",
                "properties": {"draft_id": {"type": "string"}},
                "required": ["draft_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "mail.add_label",
            "description": "Add a label to a visible message.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["message_id", "label"],
                "additionalProperties": False,
            },
        },
    )

    def __init__(
        self,
        fixture: dict[str, Any],
        recorder: EventRecorder,
    ) -> None:
        self._recorder = recorder
        self._seed = copy.deepcopy(fixture)
        self._messages = copy.deepcopy(fixture.get("messages", []))
        self._drafts = copy.deepcopy(fixture.get("drafts", []))
        self._sent = copy.deepcopy(fixture.get("sent", []))
        self._policy = copy.deepcopy(fixture.get("policy", {}))

    def definitions(self) -> tuple[dict[str, Any], ...]:
        return self.TOOL_DEFINITIONS

    def snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(
            {
                "messages": self._messages,
                "drafts": self._drafts,
                "sent": self._sent,
                "policy": self._policy,
            }
        )

    def reset(self) -> None:
        self._messages = copy.deepcopy(self._seed.get("messages", []))
        self._drafts = copy.deepcopy(self._seed.get("drafts", []))
        self._sent = copy.deepcopy(self._seed.get("sent", []))
        self._policy = copy.deepcopy(self._seed.get("policy", {}))

    def call(self, tool: str, arguments: dict[str, Any]) -> Any:
        handlers = {
            "mail.list_messages": self._list_messages,
            "mail.read_message": self._read_message,
            "mail.create_draft": self._create_draft,
            "mail.send_draft": self._send_draft,
            "mail.add_label": self._add_label,
        }
        if tool not in handlers:
            raise KeyError(f"unknown mail tool: {tool}")
        return handlers[tool](arguments)

    def _visible_message(self, message_id: str) -> dict[str, Any]:
        for message in self._messages:
            if message.get("id") != message_id:
                continue
            if message.get("protected"):
                self._recorder.record(
                    "policy_violation",
                    "mail.read_protected",
                    {"message_id": message_id},
                )
                raise ToolPolicyError(f"message is protected: {message_id}")
            return message
        raise KeyError(f"message not found: {message_id}")

    def _list_messages(self, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        requested_label = arguments.get("label")
        visible: list[dict[str, Any]] = []
        for message in self._messages:
            if message.get("protected"):
                continue
            labels = list(message.get("labels", []))
            if requested_label and requested_label not in labels:
                continue
            visible.append(
                {
                    "id": message["id"],
                    "sender": message["sender"],
                    "subject": message["subject"],
                    "labels": labels,
                    "received_at": message.get("received_at"),
                }
            )
        return visible

    def _read_message(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return copy.deepcopy(self._visible_message(str(arguments["message_id"])))

    def _create_draft(self, arguments: dict[str, Any]) -> dict[str, Any]:
        reply_to = str(arguments["in_reply_to"])
        self._visible_message(reply_to)
        draft = {
            "id": f"d-{len(self._drafts) + 1:03d}",
            "to": str(arguments["to"]),
            "subject": str(arguments["subject"]),
            "body": str(arguments["body"]),
            "in_reply_to": reply_to,
            "status": "draft",
        }
        self._drafts.append(draft)
        return copy.deepcopy(draft)

    def _send_draft(self, arguments: dict[str, Any]) -> dict[str, Any]:
        draft_id = str(arguments["draft_id"])
        if not self._policy.get("allow_send", False):
            self._recorder.record(
                "policy_violation",
                "mail.send_blocked",
                {"draft_id": draft_id},
            )
            raise ToolPolicyError("sending mail is disabled by scenario policy")
        for index, draft in enumerate(self._drafts):
            if draft.get("id") == draft_id:
                sent = copy.deepcopy(draft)
                sent["status"] = "sent"
                self._sent.append(sent)
                del self._drafts[index]
                return copy.deepcopy(sent)
        raise KeyError(f"draft not found: {draft_id}")

    def _add_label(self, arguments: dict[str, Any]) -> dict[str, Any]:
        message = self._visible_message(str(arguments["message_id"]))
        label = str(arguments["label"])
        labels = message.setdefault("labels", [])
        if label not in labels:
            labels.append(label)
            labels.sort()
        return {"message_id": message["id"], "labels": copy.deepcopy(labels)}

