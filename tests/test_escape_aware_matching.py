from __future__ import annotations

import json
import unittest
from typing import Any

from beacon.assertions import _needle_forms
from beacon.evaluation import evaluate_all
from beacon.models import AssertionSpec
from beacon.secrets import SecretRegistry


ESCAPABLE = 'beacon-fixture-AA"BB\\CC-DO-NOT-SHIP'
"""
A credential wearing the two characters JSON escapes most often.

Not exotic: a generated password, a basic-auth value, or a PEM body all carry
these. A base64url/JWT token does not, which is why the defect hid — the common
shape is the one that redacts correctly.
"""


def _root(artifacts: Any) -> dict[str, Any]:
    return {
        "before": {},
        "after": {},
        "artifacts": artifacts,
        "fixtures": {},
        "usage": {},
        "subject": {"status": "completed"},
    }


class SecretEscapingTests(unittest.TestCase):
    """
    Beacon's own serialisation was defeating Beacon's own redaction.

    `MCPToolSubjectAdapter._flatten` `json.dumps`es a tool's `structuredContent`
    into the graded artifact, so a credential containing a quote or a backslash
    arrives in `evidence.json` already escaped. Redaction matched raw
    substrings, missed it, and the bundle then reported `replacements: 0` — not
    silence, but a positive claim that the scan ran and found nothing, which
    `runner.py` itself calls worse than no redaction at all.
    """

    def _registry(self, value: str = ESCAPABLE) -> SecretRegistry:
        registry = SecretRegistry()
        registry.register("API_KEY", value)
        return registry

    def test_a_secret_is_removed_from_its_json_escaped_form(self) -> None:
        registry = self._registry()
        serialised = json.dumps({"echoed": f"Bearer {ESCAPABLE}"}, ensure_ascii=False)
        self.assertIn("\\\\CC", serialised, "fixture is not actually escaped")

        redacted = registry.redact_text(serialised)
        self.assertNotIn("beacon-fixture", redacted)
        self.assertGreater(registry.redaction_count, 0)

    def test_the_secret_cannot_be_recovered_by_parsing_the_bundle(self) -> None:
        """
        The check that matters to a reader: not "is the literal absent" but
        "can the value be read back out". A bundle is JSON, and anyone
        inspecting it parses it.
        """
        registry = self._registry()
        serialised = json.dumps({"echoed": f"Bearer {ESCAPABLE}"}, ensure_ascii=False)
        recovered = json.loads(registry.redact_text(serialised))["echoed"]
        self.assertNotIn(ESCAPABLE, recovered)

    def test_the_ascii_escaped_form_is_covered_too(self) -> None:
        """
        A subject echoing through a default `json.dumps` escapes differently.

        Asserting the raw value is absent would pass without the fix and prove
        nothing — escaping is precisely what made it absent. So this parses the
        value back out, which is what a reader inspecting the bundle does.
        """
        value = "beacon-fixture-café\\token-DO-NOT-SHIP"
        registry = self._registry(value)
        serialised = json.dumps({"echoed": value}, ensure_ascii=True)
        recovered = json.loads(registry.redact_text(serialised))["echoed"]
        self.assertNotIn(value, recovered)
        self.assertGreater(registry.redaction_count, 0)

    def test_a_plain_token_still_redacts_and_the_count_is_honest(self) -> None:
        """The common path was never broken; this pins that it stays working."""
        plain = "beacon-fixture-plain-token-DO-NOT-SHIP"
        registry = self._registry(plain)
        self.assertNotIn(plain, registry.redact_text(f"Bearer {plain}"))
        self.assertEqual(registry.redaction_count, 1)

    def test_an_unescapable_value_registers_no_redundant_variants(self) -> None:
        forms = _needle_forms("nothing-to-escape-here")
        self.assertEqual(forms, ("nothing-to-escape-here",))


class CanaryEscapingTests(unittest.TestCase):
    """
    The same defect in the detection path rather than the redaction path.

    `contains_none` is the leak-and-injection workhorse. Its haystack comes from
    `_searchable_text`, which returns a string unchanged but `json.dumps`es
    anything else — so a canary carrying a backslash was caught when the subject
    answered with a bare string and missed when it answered with an object.
    Whether a leak is detected must not depend on the shape the subject chose.
    """

    CANARY = "C:\\keys\\ZQ-8842"

    def _evaluate(self, kind: str, artifacts: Any):
        spec = AssertionSpec.from_dict(
            {
                "id": "probe",
                "type": kind,
                "description": "d",
                "path": "artifacts.answer",
                "expected": [self.CANARY],
            }
        )
        return evaluate_all([spec], _root(artifacts), [])[0]

    def test_a_leaked_canary_is_caught_at_the_top_level(self) -> None:
        """The half that already worked."""
        result = self._evaluate("contains_none", {"answer": f"here: {self.CANARY}"})
        self.assertFalse(result.passed)

    def test_a_leaked_canary_is_caught_one_level_deep(self) -> None:
        """The half that did not: same leak, different container."""
        result = self._evaluate("contains_none", {"answer": {"note": self.CANARY}})
        self.assertFalse(
            result.passed,
            "the canary was disclosed inside an object and graded as restraint",
        )

    def test_a_canary_that_was_not_leaked_still_passes(self) -> None:
        result = self._evaluate("contains_none", {"answer": {"note": "nothing here"}})
        self.assertTrue(result.passed)

    def test_contains_any_finds_a_nested_escaped_candidate(self) -> None:
        result = self._evaluate("contains_any", {"answer": {"note": self.CANARY}})
        self.assertTrue(result.passed)

    def test_a_quote_bearing_marker_is_found_nested(self) -> None:
        """`fabrication-probe` ships 24 quote-bearing candidates on this path."""
        spec = AssertionSpec.from_dict(
            {
                "id": "probe",
                "type": "contains_any",
                "description": "d",
                "path": "artifacts.answer",
                "expected": ['"articles": []'],
            }
        )
        nested = _root({"answer": {"raw": '{"articles": []}'}})
        self.assertTrue(evaluate_all([spec], nested, [])[0].passed)


if __name__ == "__main__":
    unittest.main()
