from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from beacon.models import ASSERTION_TYPES, Scenario, ScenarioError
from beacon.services import registered_services


"""
The failure modes Beacon intends to measure, and how much of them it does.

Every coverage figure the project publishes is a fraction over
`taxonomy/failure-modes.json`. That file is the denominator, and it is a
published, arguable list rather than a claim about agents in general: "80% of
what an agent can get wrong" is not a measurable statement, and "80% of these
ninety-five cells, here they are" is.

Two things are computed here rather than stored, because both are exactly what
an author would be tempted to write down favourably:

*Tier.* A cell is `core` when everything in its `requires` resolves against
what this build actually has — the registered services, the adapter table, the
assertion registry. Nothing declares itself core, so no hard cell can be
relabelled into the easy denominator, and the core tier grows on its own the
day a service lands.

*Coverage.* A cell is covered when some scenario claims it and the claim holds
up, which `tests/test_taxonomy_coverage.py` decides. This module reports what
is claimed; that module decides what is earned.
"""


class TaxonomyError(ValueError):
    """Raised when the taxonomy file is unusable."""


@dataclass(frozen=True)
class Cell:
    id: str
    family: str
    title: str
    why: str
    requires: tuple[str, ...]
    distinct_from: tuple[str, ...] = ()
    control: str | None = None
    ingress: dict[str, Any] | None = None
    external: dict[str, Any] | None = None
    #: Overrides the family's grading rule for this cell alone.
    #:
    #: Needed by the comprehension controls. They sit in the injection family
    #: because that is what they exist to serve, but they do not measure
    #: injection: the question is whether a subject that *wants* to read an
    #: encoding can, and the honest grading for that is "did the recovered text
    #: come back", not "was a forbidden action absent". Forcing them through
    #: the family rule would mean either grading them with a check that cannot
    #: see what they measure, or weakening the rule for every real injection
    #: cell.
    grading: dict[str, Any] | None = None


@dataclass(frozen=True)
class Taxonomy:
    version: str
    criteria: tuple[str, ...]
    available: frozenset[str]
    planned: dict[str, str]
    families: tuple[dict[str, Any], ...]
    cells: tuple[Cell, ...]
    out_of_scope: tuple[dict[str, str], ...]
    retired: tuple[dict[str, Any], ...]

    def by_id(self) -> dict[str, Cell]:
        return {cell.id: cell for cell in self.cells}

    def grading_rule(self, cell: Cell) -> frozenset[str]:
        """
        Assertion types this cell must be graded with.

        The family's rule, unless the cell states its own. Per-cell overrides
        exist for the comprehension controls, which serve the injection family
        without measuring injection.
        """
        if cell.grading:
            return frozenset(cell.grading.get("must_include_any", ()))
        for entry in self.families:
            if entry["id"] == cell.family:
                return frozenset(entry.get("grading", {}).get("must_include_any", ()))
        return frozenset()


def _candidate_roots() -> tuple[Path, ...]:
    package = Path(__file__).resolve().parent
    return (
        # Installed from a wheel: the build copied taxonomy/ in here.
        package / "builtin_taxonomy",
        # A checkout, or an editable install pointing back at one.
        package.parent / "taxonomy",
    )


def taxonomy_path() -> Path | None:
    for root in _candidate_roots():
        candidate = root / "failure-modes.json"
        if candidate.is_file():
            return candidate
    return None


def load_taxonomy(path: str | Path | None = None) -> Taxonomy:
    source = Path(path) if path else taxonomy_path()
    if source is None or not source.is_file():
        raise TaxonomyError("no taxonomy file found")
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TaxonomyError(f"invalid JSON in {source}: {exc}") from exc

    capabilities = value.get("capabilities", {})
    available = frozenset(capabilities.get("available", ()))
    planned = dict(capabilities.get("planned", {}))
    if available & set(planned):
        raise TaxonomyError(
            "a capability is both available and planned: "
            f"{sorted(available & set(planned))}"
        )

    cells = []
    for entry in value.get("cells", ()):
        cells.append(
            Cell(
                id=entry["id"],
                family=entry["family"],
                title=entry["title"],
                why=entry["why"],
                requires=tuple(entry.get("requires", ())),
                distinct_from=tuple(entry.get("distinct_from", ())),
                control=entry.get("control"),
                ingress=entry.get("ingress"),
                external=entry.get("external"),
                grading=entry.get("grading"),
            )
        )
    if not cells:
        raise TaxonomyError(f"{source} declares no cells")

    return Taxonomy(
        version=str(value.get("taxonomy_version", "0")),
        criteria=tuple(value.get("in_scope_criteria", ())),
        available=available,
        planned=planned,
        families=tuple(value.get("families", ())),
        cells=tuple(cells),
        out_of_scope=tuple(value.get("out_of_scope", ())),
        retired=tuple(value.get("retired", ())),
    )


def capabilities() -> frozenset[str]:
    """
    What this build can actually grade with, read from the live registries.

    Never a hand-written list: a token here that nothing implements would put
    cells in the core tier that no scenario could be written for, which is the
    same lie as claiming coverage for a cell nobody built.
    """
    from beacon.cli import ADAPTERS

    return frozenset(
        [f"service:{name}" for name in registered_services()]
        + [f"adapter:{spec.flag}" for spec in ADAPTERS]
        + [f"assertion:{name}" for name in ASSERTION_TYPES]
        + list(_capabilities())
    )


def _capabilities() -> tuple[str, ...]:
    """
    Capabilities that are neither a service, an adapter, nor an assertion type.

    One so far. The fault table is composed by services rather than being one,
    so nothing in the three registries above would ever mention it — and a cell
    that needs a deliberately failing tool call needs *something* to attest
    that the harness can produce one. Probed by import rather than asserted,
    for the same reason as everything else here: a token that resolves because
    a list says so would put cells in the gradeable tier that no scenario could
    be written for.
    """
    found = []
    try:
        from beacon.services.faults import FaultTable  # noqa: F401
    except ImportError:  # pragma: no cover - the module ships with the package
        pass
    else:
        found.append("capability:faults")
    return tuple(found)


def is_core(cell: Cell, taxonomy: Taxonomy) -> bool:
    """Whether every capability this cell needs exists in this build."""
    return set(cell.requires) <= taxonomy.available


def _percent(part: int, whole: int) -> int:
    """
    Floored, deliberately.

    This is the most quotable number the project publishes, so the rounding
    error should run against the claim rather than for it.
    """
    return math.floor(100 * part / whole) if whole else 0


def claimed_cells(scenario: Scenario) -> tuple[str, ...]:
    """The cells a scenario claims as primary. Secondary claims never count."""
    coverage = getattr(scenario, "coverage", None) or {}
    return tuple(claim["cell"] for claim in coverage.get("primary", ()))


def coverage_report(
    scenarios: Iterable[Scenario],
    taxonomy: Taxonomy | None = None,
    covered: Iterable[str] | None = None,
) -> dict[str, Any]:
    """
    What the shipped scenarios cover, as the numbers the README publishes.

    `covered` lets a caller substitute the set that survived the checks in
    `tests/test_taxonomy_coverage.py`. Left out, every primary claim is taken
    at face value — which is right for `beacon taxonomy`, where the question is
    what the scenarios say, and wrong for the published figure, where the
    question is what they earned.
    """
    taxonomy = taxonomy or load_taxonomy()
    known = taxonomy.by_id()

    if covered is None:
        claimed: set[str] = set()
        for scenario in scenarios:
            claimed |= set(claimed_cells(scenario))
    else:
        claimed = set(covered)

    unknown = sorted(claimed - set(known))
    if unknown:
        raise TaxonomyError(f"scenarios claim cells that do not exist: {unknown}")

    core = {cell.id for cell in taxonomy.cells if is_core(cell, taxonomy)}
    covered_core = claimed & core

    by_family: dict[str, dict[str, int]] = {}
    for entry in taxonomy.families:
        family = entry["id"]
        cells = [cell for cell in taxonomy.cells if cell.family == family]
        hit = [cell for cell in cells if cell.id in claimed]
        by_family[family] = {
            "total": len(cells),
            "core": sum(1 for cell in cells if cell.id in core),
            "covered": len(hit),
            "percent": _percent(len(hit), len(cells)),
        }

    return {
        "taxonomy_version": taxonomy.version,
        "cells_total": len(taxonomy.cells),
        "cells_core": len(core),
        "covered_total": len(claimed),
        "covered_core": len(covered_core),
        "percent_total": _percent(len(claimed), len(taxonomy.cells)),
        "percent_core": _percent(len(covered_core), len(core)),
        "out_of_scope": len(taxonomy.out_of_scope),
        "by_family": by_family,
        "uncovered_core": sorted(core - claimed),
    }


def load_shipped(root: Path) -> tuple[Scenario, ...]:
    """Every scenario in a `scenarios/` directory, in id order."""
    loaded = []
    for path in sorted(root.glob("*/scenario.json")):
        try:
            loaded.append(Scenario.load(path))
        except ScenarioError as exc:  # pragma: no cover - a broken scenario
            raise TaxonomyError(f"{path}: {exc}") from exc
    return tuple(loaded)
