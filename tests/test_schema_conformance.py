from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path
from typing import Any

from beacon.adapters import ReferenceInboxAdapter
from beacon.models import (
    ASSERTION_KEYS,
    ASSERTION_TYPES,
    SCENARIO_ID_PATTERN,
    SCENARIO_KEYS,
    Scenario,
    ScenarioError,
)
from beacon.runner import run_scenario


ROOT = Path(__file__).resolve().parents[1]
SCENARIO = ROOT / "scenarios" / "inbox-briefing" / "scenario.json"
SCENARIO_SCHEMA = ROOT / "schemas" / "scenario.schema.json"
EVIDENCE_SCHEMA = ROOT / "schemas" / "evidence.schema.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonschema_validate(instance: Any, schema: dict[str, Any]) -> None:
    """Full validation when the [validate] extra is installed, else skipped."""
    try:
        import jsonschema
    except ImportError:
        raise unittest.SkipTest("jsonschema is not installed")
    jsonschema.validate(instance, schema)


class SchemaAndCodeAgreeTests(unittest.TestCase):
    """
    The schemas are published contracts, and the loader enforces them in code.
    Two statements of the same rule drift apart silently unless something
    compares them, which is how `schemas/` became decorative in the first
    place. These tests are that comparison.
    """

    def test_assertion_types_match_the_published_enum(self) -> None:
        schema = _load(SCENARIO_SCHEMA)
        published = set(
            schema["properties"]["assertions"]["items"]["properties"]["type"]["enum"]
        )
        self.assertEqual(published, set(ASSERTION_TYPES))

    def test_assertion_fields_match_the_published_properties(self) -> None:
        schema = _load(SCENARIO_SCHEMA)
        published = set(
            schema["properties"]["assertions"]["items"]["properties"]
        )
        self.assertEqual(published, set(ASSERTION_KEYS))

    def test_scenario_fields_match_the_published_properties(self) -> None:
        schema = _load(SCENARIO_SCHEMA)
        self.assertEqual(set(schema["properties"]), set(SCENARIO_KEYS))

    def test_scenario_id_pattern_matches_the_published_pattern(self) -> None:
        schema = _load(SCENARIO_SCHEMA)
        self.assertEqual(
            schema["properties"]["id"]["pattern"],
            SCENARIO_ID_PATTERN.pattern,
        )

    def test_both_schemas_forbid_unknown_fields(self) -> None:
        for path in (SCENARIO_SCHEMA, EVIDENCE_SCHEMA):
            with self.subTest(schema=path.name):
                self.assertFalse(_load(path)["additionalProperties"])


class StarterScenarioTests(unittest.TestCase):
    def test_the_starter_scenario_conforms(self) -> None:
        _jsonschema_validate(_load(SCENARIO), _load(SCENARIO_SCHEMA))

    def test_the_starter_scenario_loads(self) -> None:
        scenario = Scenario.load(SCENARIO)
        self.assertTrue(SCENARIO_ID_PATTERN.match(scenario.id))


class EvidenceConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with tempfile.TemporaryDirectory() as directory:
            outcome = run_scenario(
                Scenario.load(SCENARIO),
                ReferenceInboxAdapter(),
                output_dir=directory,
                run_id="conformance",
            )
            cls.document = json.loads(
                outcome.json_path.read_text(encoding="utf-8")
            )

    def test_emitted_evidence_conforms(self) -> None:
        _jsonschema_validate(self.document, _load(EVIDENCE_SCHEMA))

    def test_every_required_field_is_present(self) -> None:
        schema = _load(EVIDENCE_SCHEMA)
        missing = set(schema["required"]) - set(self.document)
        self.assertEqual(missing, set())

    def test_no_field_is_emitted_that_the_schema_forbids(self) -> None:
        schema = _load(EVIDENCE_SCHEMA)
        extra = set(self.document) - set(schema["properties"])
        self.assertEqual(extra, set())

    def test_the_digest_matches_the_published_pattern(self) -> None:
        pattern = _load(EVIDENCE_SCHEMA)["properties"]["digest"]["pattern"]
        self.assertRegex(self.document["digest"], re.compile(pattern))

    def test_the_result_is_one_of_the_published_values(self) -> None:
        allowed = _load(EVIDENCE_SCHEMA)["properties"]["result"]["enum"]
        self.assertIn(self.document["result"], allowed)


class LoadTimeValidationTests(unittest.TestCase):
    """
    Every one of these used to be accepted, then surface mid-run as a failed
    assertion or an uncaught exception - after the subject had already done
    the work.
    """

    BASE = {
        "schema_version": "0.1",
        "id": "valid-id",
        "name": "Test",
        "description": "Test scenario",
        "goal": "Do the thing",
        "fixtures": {"mail": {}},
        "assertions": [
            {
                "id": "a",
                "type": "equals",
                "description": "x",
                "path": "after.mail.sent",
                "expected": [],
            }
        ],
    }

    def _reject(self, **patch: Any) -> str:
        value = {**self.BASE, **patch}
        with self.assertRaises(ScenarioError) as caught:
            Scenario.from_dict(value)
        return str(caught.exception)

    def test_the_base_scenario_is_actually_valid(self) -> None:
        Scenario.from_dict(dict(self.BASE))

    def test_an_id_the_schema_pattern_rejects(self) -> None:
        self.assertIn("must match", self._reject(id="BAD ID!"))

    def test_an_unknown_top_level_field(self) -> None:
        self.assertIn("unknown fields", self._reject(surprise="value"))

    def test_an_unsupported_assertion_type(self) -> None:
        message = self._reject(
            assertions=[
                {"id": "a", "type": "made_up", "description": "x", "path": "after"}
            ]
        )
        self.assertIn("unsupported type", message)
        self.assertIn("Supported types", message)

    def test_a_misspelled_assertion_field(self) -> None:
        message = self._reject(
            assertions=[
                {
                    "id": "a",
                    "type": "equals",
                    "description": "x",
                    "pathh": "after.mail",
                    "expected": 1,
                }
            ]
        )
        self.assertIn("pathh", message)

    def test_a_count_assertion_without_an_expected_value(self) -> None:
        """The exact spec that used to raise TypeError and discard the run."""
        message = self._reject(
            assertions=[
                {
                    "id": "a",
                    "type": "count_gte",
                    "description": "x",
                    "path": "after.mail.drafts",
                }
            ]
        )
        self.assertIn("requires 'expected'", message)

    def test_a_count_assertion_with_a_non_numeric_expected_value(self) -> None:
        message = self._reject(
            assertions=[
                {
                    "id": "a",
                    "type": "count_gte",
                    "description": "x",
                    "path": "after.mail.drafts",
                    "expected": "two",
                }
            ]
        )
        self.assertIn("numeric", message)

    def test_a_cites_assertion_with_a_bare_string_expected(self) -> None:
        message = self._reject(
            assertions=[
                {
                    "id": "a",
                    "type": "cites",
                    "description": "x",
                    "path": "artifacts.summary",
                    "expected": "m-001",
                }
            ]
        )
        self.assertIn("object 'expected'", message)

    def test_a_cites_assertion_without_corroborating_tokens(self) -> None:
        message = self._reject(
            assertions=[
                {
                    "id": "a",
                    "type": "cites",
                    "description": "x",
                    "path": "artifacts.summary",
                    "expected": {"id": "m-001"},
                }
            ]
        )
        self.assertIn("expected.near", message)

    def test_a_cites_assertion_with_a_nonsense_window(self) -> None:
        message = self._reject(
            assertions=[
                {
                    "id": "a",
                    "type": "cites",
                    "description": "x",
                    "path": "artifacts.summary",
                    "expected": {"id": "m-001", "near": ["x"], "window": 0},
                }
            ]
        )
        self.assertIn("positive integer", message)

    def test_an_event_assertion_without_a_target(self) -> None:
        message = self._reject(
            assertions=[
                {"id": "a", "type": "event_absent", "description": "x"}
            ]
        )
        self.assertIn("requires 'target'", message)

    def test_an_empty_path(self) -> None:
        message = self._reject(
            assertions=[
                {
                    "id": "a",
                    "type": "unchanged",
                    "description": "x",
                    "path": "   ",
                }
            ]
        )
        self.assertIn("non-empty", message)


if __name__ == "__main__":
    unittest.main()
