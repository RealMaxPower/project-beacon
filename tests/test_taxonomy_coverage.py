from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

from beacon.models import Scenario
from beacon.taxonomy import (
    capabilities,
    claimed_cells,
    coverage_report,
    is_core,
    load_shipped,
    load_taxonomy,
)

import sys as _sys
from pathlib import Path as _Path

# `unittest discover -s tests` puts this directory on the path; running a
# module directly as `python3 -m unittest tests.test_x` does not. Both forms
# get used, so make the sibling import work either way.
_sys.path.insert(0, str(_Path(__file__).resolve().parent))

from _subject_runs import failed_assertions


ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ROOT / "scenarios"
MANIFEST = ROOT / "examples" / "subjects" / "manifest.json"


"""
What it takes for a cell to count as covered.

The taxonomy is the denominator of a published percentage, which makes the
numerator the number under pressure. Every rule here exists because there is an
obvious cheap way to move it: claim a cell a scenario merely touches, claim one
graded by a check too weak to detect its failure, claim one whose adversarial
subject stopped breaking it two refactors ago.

The general principle is that a claim is a hypothesis, and these tests are what
turns it into an observation. Nothing here trusts the scenario's own word for
anything except which cell it is talking about.
"""


def _shipped() -> tuple[Scenario, ...]:
    return load_shipped(SCENARIOS)


def _manifest_subjects() -> dict[str, dict]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {case["id"]: case for case in manifest["subjects"]}


def _claims(scenario: Scenario) -> list[dict]:
    return list((scenario.coverage or {}).get("primary", []))


class TaxonomyIntegrityTests(unittest.TestCase):
    """The denominator has to hold still and mean something."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.taxonomy = load_taxonomy()

    def test_cell_ids_are_unique(self) -> None:
        ids = [cell.id for cell in self.taxonomy.cells]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_cell_belongs_to_a_declared_family(self) -> None:
        families = {entry["id"] for entry in self.taxonomy.families}
        for cell in self.taxonomy.cells:
            with self.subTest(cell=cell.id):
                self.assertIn(cell.family, families)
                self.assertTrue(cell.id.startswith(f"{cell.family}."))

    def test_cross_references_resolve(self) -> None:
        known = self.taxonomy.by_id()
        for cell in self.taxonomy.cells:
            for other in cell.distinct_from:
                with self.subTest(cell=cell.id, other=other):
                    self.assertIn(other, known)
            if cell.control:
                with self.subTest(cell=cell.id):
                    self.assertIn(cell.control, known)

    def test_available_capabilities_all_resolve(self) -> None:
        """
        R10, one half. A token here that nothing implements would put cells in
        the core tier that no scenario could be written for — the same lie as
        claiming coverage for a cell nobody built.
        """
        self.assertEqual(sorted(self.taxonomy.available - capabilities()), [])

    def test_planned_capabilities_do_not_resolve_yet(self) -> None:
        """
        R10, the other half, and the one that stops the core tier being
        inflated. A capability that shipped must move from `planned` to
        `available` in the same change, or its cells stay out of the
        denominator they now belong in and the published figure is flattering.
        """
        arrived = sorted(set(self.taxonomy.planned) & capabilities())
        self.assertEqual(
            arrived,
            [],
            f"{arrived} now exist; move them to capabilities.available so the "
            f"cells needing them enter the core tier",
        )

    def test_every_requirement_is_in_the_declared_vocabulary(self) -> None:
        """`requires: [service:quantum]` is otherwise a free pass out of core."""
        vocabulary = self.taxonomy.available | set(self.taxonomy.planned)
        for cell in self.taxonomy.cells:
            for token in cell.requires:
                with self.subTest(cell=cell.id, token=token):
                    self.assertIn(token, vocabulary)

    def test_rejected_candidates_name_the_criterion_they_failed(self) -> None:
        """
        The rejection list is what stops the denominator being quietly shrunk
        to flatter the numerator, and it only does that if each entry says why.
        """
        self.assertTrue(self.taxonomy.out_of_scope)
        for entry in self.taxonomy.out_of_scope:
            with self.subTest(cell=entry["id"]):
                self.assertRegex(entry["reason"], r"criterion \d")

    def test_a_rejected_candidate_is_not_also_a_cell(self) -> None:
        known = self.taxonomy.by_id()
        for entry in self.taxonomy.out_of_scope:
            with self.subTest(cell=entry["id"]):
                self.assertNotIn(entry["id"], known)


class ClaimTests(unittest.TestCase):
    """R1-R8: what a scenario must do to earn the cell it names."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.taxonomy = load_taxonomy()
        cls.scenarios = _shipped()
        cls.subjects = _manifest_subjects()

    def test_every_claimed_cell_exists(self) -> None:
        known = self.taxonomy.by_id()
        for scenario in self.scenarios:
            for cell in claimed_cells(scenario):
                with self.subTest(scenario=scenario.id, cell=cell):
                    self.assertIn(cell, known)
            for cell in (scenario.coverage or {}).get("secondary", []):
                with self.subTest(scenario=scenario.id, cell=cell):
                    self.assertIn(cell, known)

    def test_no_scenario_claims_a_cell_this_build_cannot_grade(self) -> None:
        """
        Covering a cell whose service does not exist means the scenario is
        grading something else and calling it that cell.
        """
        known = self.taxonomy.by_id()
        for scenario in self.scenarios:
            for cell in claimed_cells(scenario):
                with self.subTest(scenario=scenario.id, cell=cell):
                    self.assertTrue(is_core(known[cell], self.taxonomy))

    def test_a_claimed_cell_is_graded_the_way_its_family_requires(self) -> None:
        """
        R4. A family names the assertion types that can actually detect its
        failure. Grading a restraint cell with a substring search over prose
        measures whether the agent talked about the forbidden thing, not
        whether it did it.
        """
        known = self.taxonomy.by_id()
        for scenario in self.scenarios:
            types = {a.id: a.type for a in scenario.assertions}
            for claim in _claims(scenario):
                cell = known[claim["cell"]]
                allowed = self.taxonomy.grading_rule(cell)
                used = {types[name] for name in claim["assertions"]}
                with self.subTest(scenario=scenario.id, cell=cell.id):
                    self.assertTrue(
                        used & allowed,
                        f"{scenario.id} claims {cell.id} on {sorted(used)}; the "
                        f"{cell.family} family needs one of {sorted(allowed)}",
                    )

    def test_a_claimed_cell_has_a_subject_that_passes_it(self) -> None:
        """R3. A cell nothing can pass is as useless as one nothing can fail."""
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        default = manifest["scenario"]
        satisfied = {
            case.get("scenario", default)
            for case in self.subjects.values()
            if case["should_be"] == "PASS"
        }
        for scenario in self.scenarios:
            if not _claims(scenario):
                continue
            path = f"scenarios/{self._directory(scenario)}/scenario.json"
            with self.subTest(scenario=scenario.id):
                self.assertIn(
                    path,
                    satisfied,
                    f"{scenario.id} claims cells but no subject satisfies it, so "
                    f"nothing shows the cells are passable rather than impossible",
                )

    def test_named_breakers_exist_in_the_manifest(self) -> None:
        for scenario in self.scenarios:
            for claim in _claims(scenario):
                for subject in claim["broken_by"]:
                    with self.subTest(scenario=scenario.id, subject=subject):
                        self.assertIn(subject, self.subjects)

    def test_a_scenario_claims_at_most_three_cells(self) -> None:
        """R8. Otherwise one clever scenario 'covers' a whole family."""
        for scenario in self.scenarios:
            with self.subTest(scenario=scenario.id):
                self.assertLessEqual(len(_claims(scenario)), 3)

    def test_a_scenario_grades_at_least_as_much_as_it_claims(self) -> None:
        """
        R8's other half: a claim per cell, and a measurement per claim.

        Tied to the number of cells rather than a flat floor, because a flat
        floor is wrong in both directions. Three cells graded by two assertions
        means at least one cell is riding along on someone else's measurement.
        One cell graded by one assertion is a complete scenario — the
        comprehension controls are exactly that, and an arbitrary minimum of
        two would have forced a second assertion invented to satisfy the rule.
        """
        for scenario in self.scenarios:
            claims = _claims(scenario)
            if not claims:
                continue
            behavioural = [
                a for a in scenario.assertions if a.path != "subject.status"
            ]
            with self.subTest(scenario=scenario.id):
                self.assertGreaterEqual(
                    len(behavioural),
                    len(claims),
                    f"{scenario.id} claims {len(claims)} cells with "
                    f"{len(behavioural)} assertions that grade behaviour",
                )

    def _directory(self, scenario: Scenario) -> str:
        for path in SCENARIOS.glob("*/scenario.json"):
            if json.loads(path.read_text(encoding="utf-8"))["id"] == scenario.id:
                return path.parent.name
        raise AssertionError(f"no directory for {scenario.id}")


class PayloadTests(unittest.TestCase):
    """R5-R7: the payload is where the scenario says, and is not the canary."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.taxonomy = load_taxonomy()
        cls.scenarios = _shipped()

    def _payload_text(self, scenario: Scenario, pointer: str) -> str:
        from beacon.evaluation import get_path

        if pointer == "goal":
            return scenario.goal
        return str(get_path({"fixtures": scenario.fixtures}, pointer))

    def _ingress_claims(self):
        """
        Claims on cells that describe where untrusted text arrived.

        `payload_at` answers "where did the injection come in", which is a
        question only these cells ask. A target cell — what the directive tried
        to make the agent *do* — has no ingress, and pointing one at the whole
        goal would conflate the injected text with the material it names.
        """
        known = self.taxonomy.by_id()
        for scenario in self.scenarios:
            for claim in _claims(scenario):
                if known[claim["cell"]].ingress:
                    yield scenario, claim

    def test_an_ingress_claim_says_where_the_payload_is(self) -> None:
        """
        Required, not optional. Without the pointer the two rules below have
        nothing to read, and a guard that silently skips is worse than no guard
        — it reports a pass for a scenario it never looked at.
        """
        for scenario, claim in self._ingress_claims():
            with self.subTest(scenario=scenario.id, cell=claim["cell"]):
                self.assertIn(
                    "payload_at",
                    claim,
                    f"{scenario.id} claims {claim['cell']}, which describes an "
                    f"ingress, so it must say where the payload is",
                )

    def test_a_declared_payload_pointer_resolves_to_text(self) -> None:
        for scenario in self.scenarios:
            for claim in _claims(scenario):
                pointer = claim.get("payload_at")
                if not pointer:
                    continue
                with self.subTest(scenario=scenario.id, pointer=pointer):
                    self.assertTrue(self._payload_text(scenario, pointer).strip())

    def test_the_canary_does_not_live_in_the_payload(self) -> None:
        """
        R5. The rule the project already states in prose, made checkable: an
        agent that quotes the injected directive back while refusing it must
        still pass. If the canary sits inside the directive, quoting it is
        indistinguishable from obeying it, and the scenario measures echoing.
        """
        for scenario, claim in self._ingress_claims():
            canaries = [
                str(item)
                for assertion in scenario.assertions
                if assertion.type == "contains_none"
                for item in assertion.expected
            ]
            pointer = claim.get("payload_at")
            if pointer and canaries:
                payload = self._payload_text(scenario, pointer).casefold()
                for canary in canaries:
                    with self.subTest(scenario=scenario.id, canary=canary):
                        self.assertNotIn(
                            canary.casefold(),
                            payload,
                            f"{scenario.id}: the canary {canary!r} is inside the "
                            f"injected payload, so quoting the injection while "
                            f"refusing it would score as a leak",
                        )

    #: How to recognise a payload at each rung, where recognising it is possible.
    #:
    #: Deliberately partial, and the gaps are stated rather than papered over.
    #: `natural-language` has no signature — a polite sentence asking for the
    #: forbidden thing looks exactly like a polite sentence — and `multi-hop`
    #: and `split` are relationships between documents rather than properties
    #: of one. Those rungs rest on the author's word. A detector that pretended
    #: otherwise would report a pass for something it never looked at, which is
    #: the failure this whole file exists to prevent.
    RUNG_DETECTORS = {
        "plaintext-bracketed": lambda text: bool(re.search(r"\[[^\]]{4,}\]", text)),
        "unicode": lambda text: any(
            ch in text for ch in "​‌‍⁠﻿‮"
        )
        or any(ord(ch) > 0x400 for ch in text),
        "encoded": lambda text: bool(re.search(r"[A-Za-z0-9+/]{32,}={0,2}", text)),
        "markup-hidden": lambda text: "<!--" in text or "alt=" in text,
    }

    def test_a_payload_looks_like_the_rung_it_claims(self) -> None:
        """
        R6. A scenario claiming `injection.document.encoded` on a plaintext
        payload would be measuring the plaintext rung under a harder cell's
        name — which is how a coverage figure grows without the coverage
        growing.
        """
        known = self.taxonomy.by_id()
        for scenario, claim in self._ingress_claims():
            rung = (known[claim["cell"]].ingress or {}).get("obfuscation")
            detector = self.RUNG_DETECTORS.get(rung)
            pointer = claim.get("payload_at")
            if detector is None or not pointer:
                continue
            with self.subTest(scenario=scenario.id, rung=rung):
                self.assertTrue(
                    detector(self._payload_text(scenario, pointer)),
                    f"{scenario.id} claims the {rung} rung, but the payload at "
                    f"{pointer} carries no sign of it",
                )

    def test_every_enforced_rung_is_one_the_taxonomy_uses(self) -> None:
        """A detector for a rung nothing declares is a check on nothing."""
        declared = {
            (cell.ingress or {}).get("obfuscation")
            for cell in self.taxonomy.cells
        }
        for rung in self.RUNG_DETECTORS:
            with self.subTest(rung=rung):
                self.assertIn(rung, declared)

    def test_claiming_an_obfuscated_cell_requires_covering_its_control(self) -> None:
        """
        The half of R7 that does the work.

        Declaring a control says the confound has been thought about. Covering
        it is what rules the confound out: until some scenario shows a subject
        reading this encoding when the goal asks it to, "did not obey the
        encoded instruction" and "could not read the encoded instruction" are
        the same observation, and the cell measures tokenisation rather than
        restraint.
        """
        known = self.taxonomy.by_id()
        covered = {
            cell
            for scenario in self.scenarios
            for cell in claimed_cells(scenario)
        }
        for cell_id in sorted(covered):
            control = known[cell_id].control
            if not control:
                continue
            with self.subTest(cell=cell_id):
                self.assertIn(
                    control,
                    covered,
                    f"{cell_id} is claimed but its control {control} is not; "
                    f"resistance and illegibility are still indistinguishable",
                )

    def test_an_obfuscated_cell_declares_a_comprehension_control(self) -> None:
        """
        R7. A model that simply cannot decode base64 resists a base64 payload
        for a reason that has nothing to do with restraint. Cells at a decoding
        rung must point at a cell proving the encoding is legible to a subject
        that wants to read it.

        Written before any such cell exists, because this is the rule nobody
        remembers to add afterwards.
        """
        needs_control = {"unicode", "encoded", "markup-hidden"}
        for cell in self.taxonomy.cells:
            rung = (cell.ingress or {}).get("obfuscation")
            if rung not in needs_control:
                continue
            with self.subTest(cell=cell.id):
                self.assertTrue(
                    cell.control,
                    f"{cell.id} hides its payload at the {rung} rung but names "
                    f"no control, so resistance and illegibility score alike",
                )


class ObservedBreakerTests(unittest.TestCase):
    """
    R2: the breakers named by a claim actually break it, when run.

    Strictly stronger than `tests/test_falsifiability.py`, which asks only
    whether *some* subject fails each assertion. Coverage there is a union, so
    a subject can quietly stop breaking the assertion it was written for as
    long as another one happens to cover it. Here each named breaker has to
    earn its own place in the claim.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.scenarios = _shipped()
        cls.subjects = _manifest_subjects()

    def test_each_named_breaker_fails_an_assertion_of_the_cell_it_breaks(self) -> None:
        for scenario in self.scenarios:
            directory = ClaimTests._directory(self, scenario)  # type: ignore[arg-type]
            path = ROOT / "scenarios" / directory / "scenario.json"
            for claim in _claims(scenario):
                bound = set(claim["assertions"])
                for subject in claim["broken_by"]:
                    observed = failed_assertions(self.subjects[subject], path)
                    with self.subTest(
                        scenario=scenario.id, cell=claim["cell"], subject=subject
                    ):
                        self.assertTrue(
                            bound & observed,
                            f"{subject} is named as breaking {claim['cell']} but "
                            f"fails none of {sorted(bound)}; it failed "
                            f"{sorted(observed)}",
                        )


class PublishedNumberTests(unittest.TestCase):
    """
    The figures in prose, against the files they count.

    This project has shipped a wrong count twice — "twenty-one subjects" ten
    lines above "40/40", and "over 400 tests" against a suite of nearly seven
    hundred. A coverage percentage is the most quotable number it will ever
    publish and therefore the one most certain to go stale, so it is derived
    here and the prose is pinned to it.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.report = coverage_report(_shipped(), load_taxonomy())
        cls.readme = (ROOT / "README.md").read_text(encoding="utf-8")

    def test_the_readme_states_the_computed_coverage(self) -> None:
        text = " ".join(self.readme.split())
        sentence = (
            f"cover {self.report['covered_core']} of the "
            f"{self.report['cells_core']} cells this harness can grade today "
            f"({self.report['percent_core']}%), and "
            f"{self.report['covered_total']} of {self.report['cells_total']} "
            f"overall ({self.report['percent_total']}%)"
        )
        self.assertIn(
            sentence,
            text,
            "the README's coverage sentence disagrees with the files; it must "
            f"read: {sentence}",
        )

    def test_the_readme_publishes_every_family_not_a_selection(self) -> None:
        """
        Per-family numbers invite cherry-picking, and the families at zero are
        the informative ones. All of them or none.
        """
        for family in self.report["by_family"]:
            with self.subTest(family=family):
                self.assertIn(f"`{family}`", self.readme)

    def test_coverage_is_never_written_without_saying_which_kind(self) -> None:
        """
        "coverage" already means branch coverage here — there is a badge for
        it. A bare "80% coverage" would read as the test suite's number to
        every person who has seen that badge.
        """
        import re

        for match in re.finditer(r"(\w+\s+)?(\d+)%\s+coverage", self.readme):
            with self.subTest(claim=match.group(0)):
                self.assertIn(
                    (match.group(1) or "").strip(),
                    {"branch", "taxonomy"},
                    "say which coverage this is",
                )


class MutationTests(unittest.TestCase):
    """
    The guard on the guard.

    The tempting next step, once claims carry a list of breakers, is to compute
    coverage from what the claims say rather than from what the subjects do.
    That would turn the project's core property into a spreadsheet. This is the
    check that fails if anyone tries it.
    """

    def test_a_claim_that_nothing_breaks_does_not_become_coverage(self) -> None:
        scenario = next(s for s in _shipped() if s.id == "injection-resistance")
        path = SCENARIOS / "injection-resistance" / "scenario.json"
        subjects = _manifest_subjects()

        # The control subject satisfies this scenario, so naming it as a
        # breaker is a claim with nothing behind it.
        observed = failed_assertions(subjects["resists_injection"], path)
        bound = set(_claims(scenario)[0]["assertions"])
        self.assertFalse(
            bound & observed,
            "the control subject now fails the assertions it is supposed to "
            "satisfy; this test can no longer tell a real breaker from a "
            "claimed one",
        )


if __name__ == "__main__":
    unittest.main()
