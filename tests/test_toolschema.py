from __future__ import annotations

import unittest

from beacon.models import EventRecorder
from beacon.services import MailService, ToolRouter
from beacon.toolschema import (
    TOOL_NAME_PATTERN,
    ToolArgumentError,
    ToolNameError,
    validate_arguments,
    validate_tool_name,
)


SCHEMA = {
    "type": "object",
    "properties": {
        "message_id": {"type": "string"},
        "count": {"type": "integer"},
        "flag": {"type": "boolean"},
    },
    "required": ["message_id"],
    "additionalProperties": False,
}


class ValidateArgumentsTests(unittest.TestCase):
    def test_valid_arguments_pass(self) -> None:
        validate_arguments("t", SCHEMA, {"message_id": "m-001", "count": 2})

    def test_a_missing_required_argument_names_what_is_accepted(self) -> None:
        with self.assertRaises(ToolArgumentError) as caught:
            validate_arguments("t", SCHEMA, {"count": 1})
        message = str(caught.exception)
        self.assertIn("missing required", message)
        self.assertIn("message_id", message)

    def test_an_unexpected_argument_is_refused(self) -> None:
        with self.assertRaises(ToolArgumentError) as caught:
            validate_arguments("t", SCHEMA, {"message_id": "m-001", "nope": 1})
        self.assertIn("does not accept", str(caught.exception))

    def test_a_wrong_type_names_both_types(self) -> None:
        with self.assertRaises(ToolArgumentError) as caught:
            validate_arguments("t", SCHEMA, {"message_id": 7})
        message = str(caught.exception)
        self.assertIn("must be string", message)
        self.assertIn("got integer", message)

    def test_booleans_are_not_integers(self) -> None:
        with self.assertRaises(ToolArgumentError):
            validate_arguments("t", SCHEMA, {"message_id": "m", "count": True})

    def test_a_non_object_argument_payload_is_refused(self) -> None:
        with self.assertRaises(ToolArgumentError):
            validate_arguments("t", SCHEMA, ["message_id"])  # type: ignore[arg-type]

    def test_an_empty_schema_accepts_anything(self) -> None:
        validate_arguments("t", {}, {"whatever": True})


class ToolNameTests(unittest.TestCase):
    """
    Names must survive the trip to a model. The Claude API constrains the
    `tools[].name` field to `^[a-zA-Z0-9_-]{1,64}$`, and MCP names are subject
    to the same constraint when a host republishes them — so a dotted name is
    rejected at the provider boundary, and the run dies on its first tool call
    instead of producing a verdict.
    """

    def test_the_published_pattern_is_what_we_enforce(self) -> None:
        self.assertEqual(TOOL_NAME_PATTERN.pattern, r"^[a-zA-Z0-9_-]{1,64}$")

    def test_underscore_namespacing_is_accepted(self) -> None:
        for name in ("mail_list_messages", "get_weather", "tool-1", "a", "A9_-"):
            with self.subTest(name=name):
                validate_tool_name(name)

    def test_a_dotted_name_is_refused_with_the_fix_in_the_message(self) -> None:
        with self.assertRaises(ToolNameError) as caught:
            validate_tool_name("mail.list_messages")
        self.assertIn("underscores", str(caught.exception))

    def test_other_unpublishable_names_are_refused(self) -> None:
        for name in ("", "has space", "sl/ash", "colon:name", "emoji✅", "x" * 65):
            with self.subTest(name=name):
                with self.assertRaises(ToolNameError):
                    validate_tool_name(name)

    def test_every_shipped_mail_tool_is_publishable(self) -> None:
        for definition in MailService.TOOL_DEFINITIONS:
            with self.subTest(tool=definition["name"]):
                validate_tool_name(definition["name"])

    def test_registering_an_unpublishable_service_fails_at_wiring_time(self) -> None:
        class BadService:
            def definitions(self):
                return ({"name": "mail.oops", "description": "", "inputSchema": {}},)

        with self.assertRaises(ToolNameError):
            ToolRouter(EventRecorder()).register(BadService())


class RouterEnforcementTests(unittest.TestCase):
    """
    The failure a model has to recover from without being able to see the code.
    """

    def setUp(self) -> None:
        self.recorder = EventRecorder()
        self.router = ToolRouter(self.recorder)
        self.router.register(
            MailService(
                {
                    "messages": [
                        {
                            "id": "m-001",
                            "sender": "a@b.example",
                            "subject": "s",
                            "body": "b",
                            "labels": [],
                        }
                    ]
                },
                self.recorder,
            )
        )

    def test_a_malformed_call_is_distinguishable_from_a_missing_record(self) -> None:
        with self.assertRaises(ToolArgumentError) as bad_call:
            self.router.call(
                "mail_create_draft",
                {"to": "a@b.example", "subject": "s", "body": "b"},
            )
        with self.assertRaises(KeyError) as missing:
            self.router.call("mail_read_message", {"message_id": "m-404"})

        # Previously both surfaced as KeyError with a bare field or id, so a
        # subject could not tell "you called this wrong" from "it isn't there".
        self.assertIn("in_reply_to", str(bad_call.exception))
        self.assertIn("missing required", str(bad_call.exception))
        self.assertIn("not found", str(missing.exception))

    def test_a_refused_call_is_recorded_and_does_not_reach_the_service(self) -> None:
        with self.assertRaises(ToolArgumentError):
            self.router.call("mail_create_draft", {}, call_id="c1")
        kinds = [(event.kind, event.target) for event in self.recorder.events]
        self.assertIn(("tool_call", "mail_create_draft"), kinds)
        self.assertIn(("tool_error", "mail_create_draft"), kinds)
        self.assertNotIn(("tool_result", "mail_create_draft"), kinds)


if __name__ == "__main__":
    unittest.main()
