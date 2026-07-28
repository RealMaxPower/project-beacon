from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from beacon.evaluation import evaluate_assertion
from beacon.models import AssertionSpec, Scenario, ScenarioError
from beacon.outputschema import (
    SchemaError,
    describe_schema,
    validate_output,
    validate_schema,
)


ROOT = Path(__file__).resolve().parents[1]


def _paths(value: Any, schema: dict[str, Any]) -> list[str]:
    return [item.path for item in validate_output(value, schema)]


class TypeCheckingTests(unittest.TestCase):
    def test_a_matching_document_has_no_violations(self) -> None:
        schema = {"type": "object", "properties": {"a": {"type": "string"}}}
        self.assertEqual(validate_output({"a": "x"}, schema), [])

    def test_a_wrong_type_names_what_it_got(self) -> None:
        violations = validate_output(42, {"type": "string"})
        self.assertEqual(len(violations), 1)
        self.assertIn("expected string, got integer", violations[0].message)

    def test_a_boolean_is_not_an_integer(self) -> None:
        """
        True is an int subclass in Python but not in JSON Schema. Without this
        the check silently accepts a flag where a count was declared.
        """
        self.assertTrue(validate_output(True, {"type": "integer"}))
        self.assertEqual(validate_output(True, {"type": "boolean"}), [])

    def test_an_integral_float_satisfies_integer(self) -> None:
        """JSON has one number type; 3.0 off the wire is the integer 3."""
        self.assertEqual(validate_output(3.0, {"type": "integer"}), [])
        self.assertTrue(validate_output(3.5, {"type": "integer"}))

    def test_a_union_type_accepts_either_member(self) -> None:
        schema = {"type": ["object", "null"]}
        self.assertEqual(validate_output(None, schema), [])
        self.assertEqual(validate_output({}, schema), [])
        self.assertTrue(validate_output("x", schema))

    def test_null_is_not_silently_accepted_for_a_typed_field(self) -> None:
        self.assertTrue(validate_output(None, {"type": "string"}))


class ViolationReportingTests(unittest.TestCase):
    """
    The whole document, not the first problem. Fixing four violations one run
    at a time costs four runs against a live agent.
    """

    SCHEMA = {
        "type": "object",
        "required": ["items", "name"],
        "additionalProperties": False,
        "properties": {
            "name": {"type": "string", "minLength": 3},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["id"],
                    "properties": {"id": {"type": "string"}},
                },
            },
        },
    }

    def test_every_violation_is_reported(self) -> None:
        paths = _paths(
            {"name": "x", "items": [{"id": 1}, {}], "extra": True}, self.SCHEMA
        )
        self.assertEqual(
            sorted(paths), ["extra", "items[0].id", "items[1].id", "name"]
        )

    def test_a_nested_path_points_at_the_element(self) -> None:
        paths = _paths({"name": "abc", "items": [{"id": "a"}, {"id": 2}]}, self.SCHEMA)
        self.assertEqual(paths, ["items[1].id"])

    def test_a_missing_required_property_is_named(self) -> None:
        violations = validate_output({"name": "abc"}, self.SCHEMA)
        self.assertEqual(violations[0].path, "items")
        self.assertIn("required", violations[0].message)

    def test_a_wrong_type_short_circuits_its_own_subtree(self) -> None:
        """
        Reporting 'items is a string' and then twenty index errors inside a
        string it should not have walked is noise, not detail.
        """
        self.assertEqual(_paths({"name": "abc", "items": "none"}, self.SCHEMA), ["items"])


class ConstraintTests(unittest.TestCase):
    def test_string_length_bounds(self) -> None:
        self.assertTrue(validate_output("ab", {"minLength": 3}))
        self.assertEqual(validate_output("abc", {"minLength": 3}), [])
        self.assertTrue(validate_output("abcd", {"maxLength": 3}))

    def test_pattern(self) -> None:
        self.assertEqual(validate_output("projects/a", {"pattern": "^projects/"}), [])
        self.assertTrue(validate_output("hr/a", {"pattern": "^projects/"}))

    def test_numeric_bounds(self) -> None:
        self.assertTrue(validate_output(-1, {"minimum": 0}))
        self.assertEqual(validate_output(0, {"minimum": 0}), [])
        self.assertTrue(validate_output(11, {"maximum": 10}))

    def test_array_bounds_and_uniqueness(self) -> None:
        self.assertTrue(validate_output([], {"minItems": 1}))
        self.assertTrue(validate_output([1, 2, 3], {"maxItems": 2}))
        self.assertTrue(validate_output(["a", "a"], {"uniqueItems": True}))
        self.assertEqual(validate_output(["a", "b"], {"uniqueItems": True}), [])

    def test_enum_and_const(self) -> None:
        self.assertEqual(validate_output("a", {"enum": ["a", "b"]}), [])
        self.assertTrue(validate_output("c", {"enum": ["a", "b"]}))
        self.assertTrue(validate_output("c", {"const": "a"}))


class SchemaValidationTests(unittest.TestCase):
    """
    The declared schema is checked before anything is graded against it, for
    the same reason an assertion's ignored field is refused: a keyword that
    constrains nothing while reading as though it does makes the passing run
    evidence of nothing.
    """

    def test_a_misspelled_keyword_is_refused(self) -> None:
        with self.assertRaises(SchemaError) as caught:
            validate_schema({"type": "string", "minlength": 3})
        self.assertIn("minlength", str(caught.exception))

    def test_an_unknown_type_is_refused(self) -> None:
        with self.assertRaises(SchemaError):
            validate_schema({"type": "text"})

    def test_a_bad_pattern_is_refused_at_load_not_at_grade(self) -> None:
        with self.assertRaises(SchemaError):
            validate_schema({"type": "string", "pattern": "([unclosed"})

    def test_a_nested_schema_is_checked_too(self) -> None:
        with self.assertRaises(SchemaError) as caught:
            validate_schema(
                {"type": "object", "properties": {"a": {"type": "nonsense"}}}
            )
        self.assertIn("properties.a", str(caught.exception))

    def test_an_unsatisfiable_required_property_is_refused(self) -> None:
        with self.assertRaises(SchemaError):
            validate_schema(
                {
                    "type": "object",
                    "required": ["ghost"],
                    "additionalProperties": False,
                    "properties": {"real": {"type": "string"}},
                }
            )

    def test_a_non_object_schema_is_refused(self) -> None:
        with self.assertRaises(SchemaError):
            validate_schema("string")


class AssertionIntegrationTests(unittest.TestCase):
    def _evaluate(self, spec_dict: dict[str, Any], root: dict[str, Any]) -> Any:
        return evaluate_assertion(AssertionSpec.from_dict(spec_dict), root, ())

    def test_conforms_to_passes_on_a_matching_artifact(self) -> None:
        result = self._evaluate(
            {
                "id": "shape",
                "type": "conforms_to",
                "description": "d",
                "path": "artifacts.out",
                "expected": {"type": "object", "required": ["a"]},
            },
            {"artifacts": {"out": {"a": 1}}},
        )
        self.assertTrue(result.passed)

    def test_conforms_to_reports_the_violations_as_actual(self) -> None:
        result = self._evaluate(
            {
                "id": "shape",
                "type": "conforms_to",
                "description": "d",
                "path": "artifacts.out",
                "expected": {"type": "object", "required": ["a", "b"]},
            },
            {"artifacts": {"out": {}}},
        )
        self.assertFalse(result.passed)
        self.assertEqual([item["path"] for item in result.actual], ["a", "b"])

    def test_a_malformed_schema_is_refused_when_the_scenario_loads(self) -> None:
        with self.assertRaises(ScenarioError):
            AssertionSpec.from_dict(
                {
                    "id": "shape",
                    "type": "conforms_to",
                    "description": "d",
                    "path": "artifacts.out",
                    "expected": {"type": "object", "minlength": 2},
                }
            )

    def test_contains_none_passes_when_no_marker_appears(self) -> None:
        result = self._evaluate(
            {
                "id": "clean",
                "type": "contains_none",
                "description": "d",
                "path": "artifacts",
                "expected": ["SECRET-1", "SECRET-2"],
            },
            {"artifacts": {"out": "a clean summary"}},
        )
        self.assertTrue(result.passed)

    def test_contains_none_names_the_markers_it_found(self) -> None:
        result = self._evaluate(
            {
                "id": "leak",
                "type": "contains_none",
                "description": "d",
                "path": "artifacts",
                "expected": ["SECRET-1", "SECRET-2"],
            },
            {"artifacts": {"out": "here is SECRET-2 for you"}},
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.actual, ["SECRET-2"])

    def test_contains_none_searches_nested_structures(self) -> None:
        """A marker buried in a list inside an object is still a disclosure."""
        result = self._evaluate(
            {
                "id": "leak",
                "type": "contains_none",
                "description": "d",
                "path": "artifacts",
                "expected": ["SECRET-1"],
            },
            {"artifacts": {"out": {"notes": ["fine", {"deep": "SECRET-1"}]}}},
        )
        self.assertFalse(result.passed)

    def test_contains_none_ignores_case_like_contains_any(self) -> None:
        result = self._evaluate(
            {
                "id": "leak",
                "type": "contains_none",
                "description": "d",
                "path": "artifacts",
                "expected": ["secret-1"],
            },
            {"artifacts": {"out": "SECRET-1"}},
        )
        self.assertFalse(result.passed)


class DescribeSchemaTests(unittest.TestCase):
    def test_an_object_renders_its_properties_and_optionality(self) -> None:
        rendered = describe_schema(
            {
                "type": "object",
                "required": ["a"],
                "properties": {"a": {"type": "string"}, "b": {"type": "integer"}},
            }
        )
        self.assertEqual(rendered, "{a: string, b?: integer}")

    def test_an_array_renders_its_item_shape(self) -> None:
        self.assertEqual(
            describe_schema({"type": "array", "items": {"type": "string"}}),
            "array of string",
        )


class ShippedScenarioTests(unittest.TestCase):
    def test_the_new_scenarios_load(self) -> None:
        for name in (
            "injection-resistance",
            "hosted-injection-resistance",
            "web-extraction-contract",
        ):
            with self.subTest(scenario=name):
                Scenario.load(ROOT / "scenarios" / name / "scenario.json")

    def test_the_extraction_contract_accepts_what_the_agent_really_returned(self) -> None:
        """
        The schema was written from recorded runs of a live agent, so it has to
        keep accepting one. A contract nobody's output satisfies is not a
        contract, it is a broken assertion.
        """
        scenario = Scenario.load(
            ROOT / "scenarios" / "web-extraction-contract" / "scenario.json"
        )
        schema = next(
            item.expected
            for item in scenario.assertions
            if item.id == "result-matches-the-contract"
        )
        recorded = json.loads(
            (ROOT / "tests" / "stubs" / "extractor_result.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(validate_output(recorded, dict(schema)), [])

    def test_the_extraction_contract_can_fail(self) -> None:
        scenario = Scenario.load(
            ROOT / "scenarios" / "web-extraction-contract" / "scenario.json"
        )
        schema = dict(
            next(
                item.expected
                for item in scenario.assertions
                if item.id == "result-matches-the-contract"
            )
        )
        recorded = json.loads(
            (ROOT / "tests" / "stubs" / "extractor_result.json").read_text(
                encoding="utf-8"
            )
        )
        broken = dict(recorded)
        broken["primary_entities"] = "none"
        self.assertTrue(validate_output(broken, schema))


if __name__ == "__main__":
    unittest.main()
