from __future__ import annotations

import json
import unittest
from pathlib import Path

from beacon.models import Scenario

import sys as _sys
from pathlib import Path as _Path

# `unittest discover -s tests` puts this directory on the path; running a
# module directly as `python3 -m unittest tests.test_x` does not. Both forms
# get used, so make the sibling import work either way.
_sys.path.insert(0, str(_Path(__file__).resolve().parent))

from _subject_runs import failed_assertions, warm


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples" / "subjects" / "manifest.json"


HARNESS_ASSERTIONS = frozenset(
    {
        # Enforced by the usage recorder, which has its own tests. A subject
        # cannot exceed a budget the harness stops it from exceeding.
        "within-call-budget",
    }
)
"""
Assertions exempt from needing a subject that breaks them.

Kept deliberately short and explicit. The temptation with a check like this is
to widen the exemption until it passes, which converts a real guarantee into a
list of excuses.

It held three names until `task-completed` and `answered-at-all` stopped
qualifying. Both were exempt on the grounds that no badly-behaved subject could
fail them — which was a fact about the evaluator, not about the assertions:
every ending but `completed` resolved to INCOMPLETE, so a subject that stopped
to ask a human was scored the same as one that crashed. With escalation graded
rather than swallowed, a subject that finishes the work and then asks an
unnecessary question fails both, and the exemption had to go.
"""


_failed_assertions = failed_assertions


class FalsifiabilityTests(unittest.TestCase):
    """
    Every behavioural assertion must have a subject that makes it fail.

    CONTRIBUTING has required this since the first release and the project
    still shipped assertions nothing could break — two in the starter scenario
    at the beginning, and `messages-preserved` later, which became
    unfalsifiable as a *side effect* of correctly removing a tool that was a
    trap. Both times the prose rule was in place and both times it was missed,
    because nobody was running the check. This runs it.

    What an unfalsifiable assertion costs: report.md prints its description as
    a finding. "Original messages were preserved" reads as a safety result
    when no tool on the surface could have altered a message.
    """

    @classmethod
    def setUpClass(cls) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        default = manifest["scenario"]
        cases = [
            (case, ROOT / case.get("scenario", default))
            for case in manifest["subjects"]
        ]
        # This is the first harness to ask, so it pays for the batch. Every
        # later caller — here and in the other modules — reads it from cache.
        warm(cases)
        cls.broken: dict[str, set[str]] = {}
        for case, path in cases:
            key = case.get("scenario", default)
            cls.broken.setdefault(key, set())
            cls.broken[key] |= _failed_assertions(case, path)

    def test_every_behavioural_assertion_has_a_subject_that_breaks_it(self) -> None:
        for path in sorted(self.broken):
            scenario = Scenario.load(ROOT / path)
            declared = {item.id for item in scenario.assertions}
            unproven = sorted(declared - self.broken[path] - HARNESS_ASSERTIONS)
            with self.subTest(scenario=scenario.id):
                self.assertEqual(
                    unproven,
                    [],
                    f"{scenario.id}: no subject makes these fail, so the "
                    f"report states them without having tested them",
                )

    def test_every_shipped_scenario_is_covered_by_the_manifest(self) -> None:
        """
        A scenario with no adversarial subject at all is the easy way to pass
        the check above without having earned it.
        """
        shipped = {
            f"scenarios/{path.parent.name}/scenario.json"
            for path in (ROOT / "scenarios").glob("*/scenario.json")
        }
        self.assertEqual(shipped - set(self.broken), set())

    # Every `limits` key something in `beacon/` actually reads. The schema
    # types this block as a bare object with no properties, so a typo or an
    # invented setting is accepted silently and published into evidence.
    ENFORCED_LIMITS = frozenset(
        {
            "timeout_seconds",
            "max_protocol_messages",
            "max_subject_calls",
            "max_subject_seconds",
            "max_tool_calls",
        }
    )

    def test_no_scenario_declares_a_limit_nothing_reads(self) -> None:
        """
        `estimated_cost_usd: 0.25` sat in two scenarios and was read by no
        code. It reached every bundle they produced, because `limits` is copied
        wholesale into evidence — a dollar figure published beside measured
        numbers, never checked, and certain to drift as prices move.

        The same hole passes a misspelled `timeout_second`, which silently
        gives the run the 30-second default instead of what it says.
        """
        for path in sorted((ROOT / "scenarios").glob("*/scenario.json")):
            declared = set(json.loads(path.read_text(encoding="utf-8")).get("limits", {}))
            with self.subTest(scenario=path.parent.name):
                self.assertEqual(
                    declared - self.ENFORCED_LIMITS,
                    set(),
                    "declares limits nothing enforces; they publish into "
                    "evidence looking like controls",
                )

    def test_the_enforced_list_is_not_stale(self) -> None:
        """A guard listing names nothing reads would pass while checking air."""
        source = "".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / "beacon").rglob("*.py")
        )
        for name in self.ENFORCED_LIMITS:
            with self.subTest(limit=name):
                self.assertIn(f'"{name}"', source)

    def test_a_declared_budget_is_one_the_adapter_can_enforce(self) -> None:
        """
        `max_subject_calls` counts requests Beacon makes *to* a subject, so it
        binds only where Beacon drives: the A2A and MCP-tool adapters. A
        command or MCP-host subject drives itself and is bounded by
        `timeout_seconds` and `max_protocol_messages`.

        `injection-resistance` declared a call budget of 2 that never fired,
        and `docs/running-it-yourself.md` cited the same setting as the guard
        against a runaway model bill on a command subject. A limit published
        into evidence and never applied is a control that reads as protection
        and provides none.
        """
        for path in sorted((ROOT / "scenarios").glob("*/scenario.json")):
            scenario = json.loads(path.read_text(encoding="utf-8"))
            if "max_subject_calls" not in scenario.get("limits", {}):
                continue
            kind = scenario.get("metadata", {}).get("subject_kind", "")
            with self.subTest(scenario=path.parent.name):
                self.assertIn(
                    "hosted",
                    kind,
                    f"{path.parent.name} declares max_subject_calls but its "
                    f"subject_kind is {kind!r}; only a subject Beacon drives "
                    f"has that budget enforced",
                )

    def test_a_tool_budget_is_declared_only_where_tools_are_routed(self) -> None:
        """
        The mirror of the rule above. `max_tool_calls` is counted by the tool
        router, so it binds only where the subject's calls come back through
        Beacon. A black-box subject — one Beacon sends a task to and reads an
        answer from — never routes a tool call here, so the ceiling would be
        published into evidence and never reached: a control that reads as
        protection and provides none, which is the exact defect
        `estimated_cost_usd` and the unfired call budget both were.
        """
        for path in sorted((ROOT / "scenarios").glob("*/scenario.json")):
            scenario = json.loads(path.read_text(encoding="utf-8"))
            if "max_tool_calls" not in scenario.get("limits", {}):
                continue
            kind = scenario.get("metadata", {}).get("subject_kind", "")
            with self.subTest(scenario=path.parent.name):
                self.assertNotIn(
                    "hosted",
                    kind,
                    f"{path.parent.name} declares max_tool_calls but its "
                    f"subject_kind is {kind!r}; a hosted subject calls no tools "
                    f"through Beacon, so nothing would ever count against it",
                )

    def test_the_exemption_list_is_not_quietly_growing(self) -> None:
        """
        Pins the exemptions by name. Widening this set is how a guarantee
        turns into a formality, so it should take a deliberate edit and show
        up in review.

        It has shrunk once, which is the direction worth noting. `task-completed`
        and `answered-at-all` were exempt because "an adversarial subject cannot
        make them FAIL by behaving badly, only by not running" — true only while
        every ending except `completed` resolved to INCOMPLETE. Once escalation
        became an ending the evaluator would grade,
        `examples/subjects/escalates_unnecessarily.py` could make both go red by
        doing the work and then stopping to ask a question it did not need to
        ask, and the exemption stopped being earned.
        """
        self.assertEqual(HARNESS_ASSERTIONS, frozenset({"within-call-budget"}))

    def test_each_exempt_assertion_really_is_a_harness_property(self) -> None:
        """An exemption is only honest if the assertion exists somewhere."""
        declared: set[str] = set()
        for path in (ROOT / "scenarios").glob("*/scenario.json"):
            declared |= {item.id for item in Scenario.load(path).assertions}
        self.assertEqual(HARNESS_ASSERTIONS - declared, set())


class CitationDesignTests(unittest.TestCase):
    """
    A `cites` assertion whose corroborating token sits inside the reference is
    satisfied by naming the reference — the name-drop the type exists to
    reject. Two shipped assertions had this, caught by a subject that listed
    every document path and read none of them.
    """

    def test_no_corroborating_token_hides_inside_its_own_reference(self) -> None:
        for path in sorted((ROOT / "scenarios").glob("*/scenario.json")):
            scenario = Scenario.load(path)
            for item in scenario.assertions:
                if item.type != "cites":
                    continue
                reference = str(item.expected["id"]).casefold()
                with self.subTest(scenario=scenario.id, assertion=item.id):
                    inside = [
                        token
                        for token in item.expected["near"]
                        if str(token).casefold() in reference
                    ]
                    self.assertEqual(inside, [])


if __name__ == "__main__":
    unittest.main()
