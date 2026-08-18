from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace

from beacon.cli import main
from beacon.falsifiability import (
    Subject,
    discover_subjects,
    proof_from,
    prove,
    unfalsifiable_by_construction,
)
from beacon.models import AssertionSpec, Scenario, ScenarioError
from beacon.scaffold import scaffold


ROOT = Path(__file__).resolve().parents[1]


def _evidence(assertions: list[dict]) -> SimpleNamespace:
    """Just enough of a bundle for `proof_from`, which reads one field."""
    return SimpleNamespace(assertions=assertions)


class ProofDefinitionTests(unittest.TestCase):
    """
    What counts as having watched an assertion fail.

    This is the whole feature in one predicate. If an unmeasured result counts,
    the check inverts: a subject that crashes proves every assertion in the
    scenario falsifiable, so the worst-behaved possible subject certifies the
    most. The suite shipped exactly that — `tests/_subject_runs.py` collected
    `not item["passed"]` with no `measured` check, and
    `examples/subjects/crashes_midrun.py` supplied false proof for four
    assertions under it.

    It is the same distinction 0.2.0 threaded through the determinism signature,
    the baseline denominator and the repeat set, arriving last in the guard whose
    entire job is to establish that somebody watched a failure.
    """

    def test_a_measured_failure_is_proof(self) -> None:
        self.assertEqual(
            proof_from(_evidence([{"id": "a", "passed": False, "measured": True}])),
            {"a"},
        )

    def test_an_unmeasured_failure_is_not(self) -> None:
        self.assertEqual(
            proof_from(_evidence([{"id": "a", "passed": False, "measured": False}])),
            set(),
            "a run Beacon could not evaluate says nothing about whether the "
            "assertion can fail",
        )

    def test_a_pass_is_not_proof(self) -> None:
        self.assertEqual(
            proof_from(_evidence([{"id": "a", "passed": True, "measured": True}])),
            set(),
        )

    def test_a_bundle_without_the_field_is_read_as_measured(self) -> None:
        """
        Older bundles predate `measured` being written out. Treating a missing
        flag as measured keeps them readable, and matches every other reader in
        the codebase.
        """
        self.assertEqual(proof_from(_evidence([{"id": "a", "passed": False}])), {"a"})


class UnfalsifiableByConstructionTests(unittest.TestCase):
    """
    Some assertions cannot fail whatever a subject does, and no number of
    subjects will reveal it.

    `count_gte path 0` is satisfied by every list including the empty one. It
    has no failing case, so it can only ever come back *unmeasured* — and under
    the loose definition of proof, the subjects that omitted the field were
    counted as having broken it. `contract-empty-result` shipped that.

    Reported separately from "no subject broke it" because the fix is different:
    writing another subject cannot help.
    """

    @staticmethod
    def _spec(kind: str, expected: object) -> AssertionSpec:
        return AssertionSpec(id="a", type=kind, description="d", path="x", expected=expected)

    def test_a_floor_of_zero_cannot_fail(self) -> None:
        for kind in ("count_gte", "length_gte", "event_count_gte"):
            with self.subTest(type=kind):
                self.assertIsNotNone(unfalsifiable_by_construction(self._spec(kind, 0)))

    def test_a_negative_floor_cannot_fail_either(self) -> None:
        self.assertIsNotNone(unfalsifiable_by_construction(self._spec("count_gte", -1)))

    def test_a_real_floor_can(self) -> None:
        self.assertIsNone(unfalsifiable_by_construction(self._spec("count_gte", 1)))

    def test_a_ceiling_is_left_alone(self) -> None:
        """`count_lte 0` is falsifiable — any non-empty list breaks it."""
        self.assertIsNone(unfalsifiable_by_construction(self._spec("count_lte", 0)))

    def test_no_shipped_scenario_carries_one(self) -> None:
        """The repository's own state, which is what found this."""
        offenders = [
            f"{path.parent.name}/{spec.id}"
            for path in sorted((ROOT / "scenarios").glob("*/scenario.json"))
            for spec in Scenario.load(path).assertions
            if spec.falsifiable and unfalsifiable_by_construction(spec)
        ]
        self.assertEqual(offenders, [])


class ExemptionTests(unittest.TestCase):
    """
    An exemption is declared where a reader of the scenario sees it.

    This lived as a frozenset inside `tests/test_falsifiability.py`, which is
    the right idea in the wrong place: the fact belongs to the assertion, and a
    user's own scenario had no way to say it at all.
    """

    BASE = {"id": "a", "type": "equals", "description": "d", "path": "x", "expected": 1}

    def test_an_exemption_needs_a_reason(self) -> None:
        with self.assertRaises(ScenarioError) as caught:
            AssertionSpec.from_dict({**self.BASE, "falsifiable": False})
        self.assertIn("falsifiable_reason", str(caught.exception))

    def test_a_reason_without_an_exemption_is_refused(self) -> None:
        """It would be silently ignored, which is how a scenario lies quietly."""
        with self.assertRaises(ScenarioError):
            AssertionSpec.from_dict({**self.BASE, "falsifiable_reason": "because"})

    def test_assertions_are_falsifiable_by_default(self) -> None:
        self.assertTrue(AssertionSpec.from_dict(self.BASE).falsifiable)

    def test_an_exempt_assertion_is_not_reported_as_unproven(self) -> None:
        scenario = Scenario.load(ROOT / "scenarios" / "fabrication-probe" / "scenario.json")
        exempt = {s.id for s in scenario.assertions if not s.falsifiable}
        self.assertIn("within-call-budget", exempt)
        report = prove(scenario, [])
        self.assertNotIn("within-call-budget", report.unproven)


class ProveEndToEndTests(unittest.TestCase):
    """
    The command a user actually runs, on the scenario `init` actually writes.

    Driven through `main()` rather than the module, because the convention —
    subjects live in `subjects/` beside the scenario — is the part that only
    exists in the CLI, and it is what makes `beacon prove <scenario>` work with
    no flags on a freshly scaffolded probe.
    """

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)
        scaffold("my-probe", self.root)
        self.scenario = self.root / "my-probe" / "scenario.json"

    def _run(self, *argv: str) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            code = main(["prove", str(self.scenario), *argv])
        return code, out.getvalue()

    def test_it_finds_the_scaffolded_subjects_without_flags(self) -> None:
        found = {s.label for s in discover_subjects(self.scenario)}
        self.assertEqual(found, {"compliant.py", "violating.py"})

    def test_a_scaffold_is_red_and_says_which(self) -> None:
        """
        Deliberate, and the scaffold README says so. `violating.py` breaks
        exactly one assertion, so the others are unproven the moment the
        scenario is generated — the state the README warns about, made visible
        rather than left to be noticed.
        """
        code, output = self._run()
        self.assertEqual(code, 1)
        self.assertIn("systems-grounded", output)
        self.assertIn("broken by violating.py", output)
        self.assertIn("UNPROVEN", output)

    def test_it_goes_green_once_every_assertion_has_a_breaker(self) -> None:
        """
        The other direction, which is the one that matters for a CI gate. A
        command that can only ever be red is not a gate, it is a warning.
        """
        scenario = json.loads(self.scenario.read_text(encoding="utf-8"))
        scenario["assertions"] = [
            item for item in scenario["assertions"] if item["id"] == "systems-grounded"
        ]
        self.scenario.write_text(json.dumps(scenario, indent=2), encoding="utf-8")
        code, output = self._run()
        self.assertEqual(code, 0, output)
        self.assertNotIn("UNPROVEN", output)

    def test_no_subjects_is_an_error_rather_than_a_green_result(self) -> None:
        """
        Reporting "0 unproven" over an empty subject set is the vacuous pass
        this command exists to find. It would be the funniest possible bug to
        ship here.
        """
        shutil.rmtree(self.scenario.parent / "subjects")
        code, output = self._run()
        self.assertEqual(code, 2)
        self.assertIn("no subjects", output)

    def test_explicit_subjects_override_the_convention(self) -> None:
        code, output = self._run(
            "--subject", str(self.scenario.parent / "subjects" / "compliant.py")
        )
        self.assertEqual(code, 1)
        self.assertIn("against 1 subject", output)

    def test_json_output_is_machine_readable(self) -> None:
        code, output = self._run("--json")
        self.assertEqual(code, 1)
        payload = json.loads(output)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["broken_by"]["systems-grounded"], ["violating.py"])
        self.assertIn("task-completed", payload["unproven"])


class ScaffoldServiceNameTests(unittest.TestCase):
    """
    `init --service files` generated a scenario whose own README could not run.

    The name collides with a Beacon service, so `--service-module` failed with
    "a different service is already registered as 'files'" — from the exact
    command the generated README printed. Found by pointing `prove` at it, which
    is the sort of thing a new command surfaces.
    """

    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_a_builtin_service_name_is_refused(self) -> None:
        for name in ("files", "mail", "shell"):
            with self.subTest(service=name):
                with self.assertRaises(ScenarioError) as caught:
                    scaffold(f"probe-{name}", self.root, service=name)
                self.assertIn("already a Beacon service", str(caught.exception))

    def test_a_name_of_your_own_still_works(self) -> None:
        created = scaffold("probe-notes", self.root, service="notes")
        self.assertTrue(any(p.name == "service.py" for p in created))


if __name__ == "__main__":
    unittest.main()
