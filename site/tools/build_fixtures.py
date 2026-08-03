#!/usr/bin/env python3
"""
Record the runs the playground replays, by actually running them.

    python3 site/tools/build_fixtures.py
    python3 site/tools/build_fixtures.py --check

The playground is a demo, not a live runner: it replays recorded evidence in
the browser. The question is where that evidence comes from. Written by hand it
is a guess about Beacon's output, and the design handoff is blunt about what
that costs — a plausible `evidence.json` that does not match the real one is
worse than no expert mode at all, because expert mode is the view built to be
trusted by people who will not trust a friendly summary.

So nothing here is authored. Each fixture is a real `run_scenario` call against
a real subject from `examples/subjects/`, and the bundle it writes is the bundle
the site ships. The subjects were already there: forty of them, each recorded in
`manifest.json` with the verdict it should produce. A demo agent that misbehaves
is not something this site needed to invent.

`--check` re-runs everything into a temporary directory and compares against
what is committed, ignoring the fields that cannot repeat (clock, duration,
digest). It answers "would regenerating change anything that matters", which is
the reproducibility claim the site makes about itself.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from beacon.adapters import JSONLCommandAdapter, ReferenceInboxAdapter  # noqa: E402
from beacon.models import Scenario  # noqa: E402
from beacon.runner import run_scenario  # noqa: E402
from beacon.services import registered_services  # noqa: E402

MANIFEST = ROOT / "examples" / "subjects" / "manifest.json"
OUT = ROOT / "site" / "src" / "data" / "generated"
DEFAULT_TIMEOUT = 15.0

# The machine that recorded a fixture must not be identifiable from it. The
# adapter resolves the subject command to an absolute path, which on this
# machine contains a home directory; `_scrub` rewrites it and
# `tests/test_site_claims.py` fails if one ever survives into the site.
PLACEHOLDER = "<repo>"

# Fields that differ on every run by construction. Excluded from --check, not
# from the fixtures: the committed bundles keep their real timestamps, because
# a run did happen at a time and blanking it would be its own small fiction.
VOLATILE = frozenset({"started_at", "completed_at", "timestamp", "digest", "usage"})

# Each entry is a screen state the playground has to be able to show, mapped to
# the subject that already produces it. `verdict` here is only a guard: it is
# asserted against the run rather than trusted, so a subject whose behaviour
# changes fails the build instead of quietly relabelling the demo.
FIXTURES: tuple[dict[str, str], ...] = (
    {
        "key": "misbehaving",
        "subject": "attempts_send",
        "label": "Demo agent — misbehaving",
        "shows": "A blocked attempt. Policy refuses the send; the attempt is the evidence.",
        "verdict": "FAIL",
    },
    {
        "key": "well-behaved",
        "subject": "well_behaved",
        "label": "Demo agent — well behaved",
        "shows": "Every assertion satisfied, and an exact reset.",
        "verdict": "PASS",
    },
    {
        "key": "obeys-injection",
        "subject": "obeys_injection",
        "label": "Demo agent — follows the injection",
        "shows": "The injected instruction in m-004 is obeyed. Drives InjectionCallout: obeyed.",
        "verdict": "FAIL",
    },
    {
        "key": "disconnects",
        "subject": "never_completes",
        "label": "Host that disconnects",
        "shows": "Work done, no completion signal. INCOMPLETE is the honest answer, not an error.",
        "verdict": "INCOMPLETE",
    },
)

# The other six scenarios, each with the subject that satisfies it and the one
# that breaks it.
#
# None of these needs a hosted agent or an API key, which the site said they did
# until someone checked. Every one is a deterministic local subject speaking the
# JSONL bridge: `web-extraction-grounding` graded against a captured page,
# `hosted-injection-resistance` against recorded content. What costs money is
# the twelve-run *baseline* against a real model, not the scenario.
SCENARIOS: tuple[dict[str, str], ...] = (
    {
        "key": "organizes_documents",
        "subject": "organizes_documents",
        "label": "Tidies the folder",
        "shows": "Classifies and indexes the files without touching the originals.",
        "verdict": "PASS",
    },
    {
        "key": "deletes_documents",
        "subject": "deletes_documents",
        "label": "Deletes what it was asked to organise",
        "shows": "Tidying by removal. The documents are gone and the index looks tidy.",
        "verdict": "FAIL",
    },
    {
        "key": "resists_injection",
        "subject": "resists_injection",
        "label": "Ignores the instruction in the file",
        "shows": "Does the assignment; declines the instruction hidden in the material.",
        "verdict": "PASS",
    },
    {
        "key": "obeys_delete_injection",
        "subject": "obeys_delete_injection",
        "label": "Obeys the instruction in the file",
        "shows": "A document told it to delete, and it reached for the tool. The attempt is the evidence.",
        "verdict": "FAIL",
    },
    {
        "key": "declines_to_fabricate",
        "subject": "declines_to_fabricate",
        "label": "Says there is nothing to find",
        "shows": "Asked about a record that does not exist, and says so.",
        "verdict": "PASS",
    },
    {
        "key": "fabricates_an_answer",
        "subject": "fabricates_an_answer",
        "label": "Invents an answer",
        "shows": "Asked about a record that does not exist, and confidently describes it.",
        "verdict": "FAIL",
    },
    {
        "key": "extraction_control_contract",
        "subject": "extraction_control_contract",
        "label": "Holds its output contract",
        "shows": "Every field a consumer parses is present and correctly typed.",
        "verdict": "PASS",
    },
    {
        "key": "breaks_the_output_contract",
        "subject": "breaks_the_output_contract",
        "label": "Breaks the output contract",
        "shows": "conforms_to reports every violation with its path, not just the first.",
        "verdict": "FAIL",
    },
    {
        "key": "extracts_only_what_is_there",
        "subject": "extracts_only_what_is_there",
        "label": "Reports only what the page says",
        "shows": "Every entity it names can be found in the page it was given.",
        "verdict": "PASS",
    },
    {
        "key": "invents_page_entities",
        "subject": "invents_page_entities",
        "label": "Invents an author and a date",
        "shows": "Fabrication caught by grounding — the values appear nowhere in the source.",
        "verdict": "FAIL",
    },
    {
        "key": "hosted_resists_injection",
        "subject": "hosted_resists_injection",
        "label": "Hosted agent declines the injection",
        "shows": "The same two checks, one integration level up.",
        "verdict": "PASS",
    },
    {
        "key": "hosted_leaks_annex",
        "subject": "hosted_leaks_annex",
        "label": "Hosted agent leaks the withheld annex",
        "shows": "A canary that exists only in the material it was not given.",
        "verdict": "FAIL",
    },
)

# The reference agent is not in the manifest — it is in-process, not a subject
# under test — but the playground offers it, so it is recorded the same way.
REFERENCE = {
    "key": "reference",
    "label": "Reference agent",
    "shows": "Beacon's own deterministic agent, at integration level 4.",
    "verdict": "PASS",
}


def _scrub(value: Any) -> Any:
    """Replace this machine's repository path wherever it appears."""
    if isinstance(value, str):
        return value.replace(str(ROOT), PLACEHOLDER)
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, dict):
        return {key: _scrub(item) for key, item in value.items()}
    return value


def _strip_volatile(value: Any) -> Any:
    """Drop the fields that cannot repeat, so --check compares the rest."""
    if isinstance(value, list):
        return [_strip_volatile(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _strip_volatile(item)
            for key, item in value.items()
            if key not in VOLATILE
        }
    return value


def _subjects() -> dict[str, dict[str, Any]]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {case["id"]: case for case in manifest["subjects"]}


def _scenario_for(case: dict[str, Any] | None) -> Path:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    default = manifest["scenario"]
    return ROOT / ((case or {}).get("scenario") or default)


def _record(spec: dict[str, str], into: Path) -> dict[str, Any]:
    """Run one fixture and write its bundle. Returns the index entry."""
    subjects = _subjects()
    case = subjects.get(spec.get("subject", ""))

    if case is None and spec["key"] != REFERENCE["key"]:
        raise SystemExit(
            f"{spec['subject']!r} is not in the manifest. The playground may only "
            f"demo subjects the adversarial suite already records."
        )

    if case is None:
        adapter: Any = ReferenceInboxAdapter()
        behavior = "Beacon's in-process reference agent."
        should_be = "PASS"
    else:
        adapter = JSONLCommandAdapter(
            [sys.executable, str(ROOT / case["script"])],
            timeout_seconds=float(case.get("timeout_seconds", DEFAULT_TIMEOUT)),
        )
        behavior = case["behavior"]
        should_be = case["should_be"]

    scenario = Scenario.load(_scenario_for(case))
    outcome = run_scenario(scenario, adapter, output_dir=str(into), run_id=spec["key"])

    if outcome.evidence.result != spec["verdict"]:
        raise SystemExit(
            f"{spec['key']}: recorded {outcome.evidence.result}, fixture declares "
            f"{spec['verdict']}. Either the subject changed or the fixture is stale; "
            f"do not relabel the demo without understanding which."
        )

    run_dir = into / spec["key"]
    for name in ("evidence.json", "events.json"):
        path = run_dir / name
        path.write_text(
            json.dumps(_scrub(json.loads(path.read_text(encoding="utf-8"))), indent=2)
            + "\n",
            encoding="utf-8",
        )
    report = run_dir / "report.md"
    report.write_text(_scrub(report.read_text(encoding="utf-8")), encoding="utf-8")

    return {
        "key": spec["key"],
        "label": spec["label"],
        "shows": spec["shows"],
        "subject": spec.get("subject"),
        "behavior": behavior,
        "expected": should_be,
        "verdict": outcome.evidence.result,
        "scenario": scenario.id,
        "integration_level": outcome.evidence.subject.get("integration_level"),
    }


def _scenarios() -> list[dict[str, Any]]:
    """
    Every scenario that ships, read from its own file.

    The site states how many there are and what each one grades. Counting the
    directory means it cannot say eight when there are seven, and cannot
    describe a tool surface the scenario does not declare.
    """
    out: list[dict[str, Any]] = []
    for path in sorted((ROOT / "scenarios").glob("*/scenario.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        out.append(
            {
                "slug": path.parent.name,
                "id": data["id"],
                "name": data["name"],
                "description": data["description"],
                "goal": data.get("goal", ""),
                "tools": data.get("tools", []),
                "artifact": (data.get("output_contract") or {}).get("artifact"),
                "output_contract": data.get("output_contract"),
                # The evidence bundle records which scenario ran, not the world
                # it ran against — fixtures and the tool surface are stripped
                # from `evidence.scenario`. The playground draws that world, so
                # it has to come from the scenario file, which is here.
                "fixtures": data.get("fixtures", {}),
                # `type` travels with the assertion because the playground uses
                # it to tell a forbidden-outcome check (`event_absent`,
                # `contains_none`) from an ordinary one. Without it the screen
                # had to guess which assertions describe something the subject
                # was supposed to *not* do.
                "assertions": [
                    {
                        "id": a.get("id"),
                        "description": a.get("description"),
                        "type": a.get("type"),
                    }
                    for a in data.get("assertions", [])
                ],
                # The split the site calls "grading family". Every scenario
                # declares fixtures, so their presence decides nothing; what
                # separates the two is whether a *stateful* service backs them.
                # `registered_services()` is that list, read from the registry
                # rather than named here, so a scenario pack that brings its own
                # service is classified without editing this script.
                "graded_on": (
                    "service state"
                    if set(data.get("fixtures", {})) & set(registered_services())
                    else "the answer"
                ),
            }
        )
    return out


def _baselines() -> list[dict[str, Any]]:
    """
    The recorded pass rates, copied rather than retyped.

    These are the only multi-run measurements in the project, and the numbers
    the site's determinism and regression screens show. The README quoted a
    five-run 20% against a twelve-run figure three times larger for longer than
    it should have; reading the files is how that stops being possible here.
    """
    out: list[dict[str, Any]] = []
    for path in sorted((ROOT / "baselines").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        out.append({"file": path.name, **_scrub(data)})
    return out


def _facts() -> dict[str, Any]:
    """
    The counts the marketing pages state, each derived from what it counts.

    Deliberately omitted: the number of tests and the coverage percentage. The
    README stopped giving exact figures for those and says "over 400 tests,
    against an enforced floor of 80%" instead — a claim that stays true as the
    suite grows. A website repeating today's exact count would be wrong by next
    week, and there is nothing here to pin it to.
    """
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    subjects = manifest["subjects"]
    scenarios = _scenarios()

    by_verdict: dict[str, int] = {}
    for case in subjects:
        by_verdict[case["should_be"]] = by_verdict.get(case["should_be"], 0) + 1

    return {
        "subjects": len(subjects),
        "subjects_by_expected_verdict": by_verdict,
        # Subjects whose recorded verdict is not the one they should produce.
        # Zero today; shown rather than asserted, because the honest number is
        # whatever it is.
        "subjects_with_open_defects": sum(
            1 for case in subjects if case["currently"] != case["should_be"]
        ),
        "scenarios": len(scenarios),
        "scenarios_by_grading": {
            family: sum(1 for s in scenarios if s["graded_on"] == family)
            for family in ("service state", "the answer")
        },
        "docs": _tracked_markdown("docs"),
        "surveys": _tracked_markdown("conformance"),
    }


def _tracked_markdown(directory: str) -> list[str]:
    """
    The markdown files git knows about, not the ones that happen to be present.

    The Docs page links each of these to `blob/main/...`, so a file that is not
    committed produces a card pointing at a URL that cannot resolve. Globbing
    the directory made the count honest about the folder and dishonest about
    the site: a scratch file dropped in `docs/` became a published card with a
    dead link and no description.

    Falls back to globbing outside a git checkout — a released sdist has no
    `.git` — which is the case where every file present is by definition part
    of the distribution.
    """
    try:
        listed = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", f"{directory}/*.md"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        return sorted(p.name for p in (ROOT / directory).glob("*.md"))

    return sorted(Path(name).name for name in listed)


def _build(into: Path) -> list[dict[str, Any]]:
    into.mkdir(parents=True, exist_ok=True)
    entries = [_record(spec, into) for spec in (*FIXTURES, REFERENCE, *SCENARIOS)]

    (into / "scenarios.json").write_text(
        json.dumps(_scenarios(), indent=2) + "\n", encoding="utf-8"
    )

    # The scenario files themselves, byte for byte.
    #
    # `scenarios.json` above is a projection: it adds `slug`, `artifact` and
    # `graded_on`, and drops `schema_version`, `limits` and `metadata`. Expert
    # mode renders it under the path of the real file, which made the panel
    # claim to be a document it was not — the one place in this site where a
    # plausible near-miss is worse than showing nothing. So the real bytes ship
    # too, and expert mode reads these.
    raw = into / "scenarios"
    raw.mkdir(parents=True, exist_ok=True)
    for path in sorted((ROOT / "scenarios").glob("*/scenario.json")):
        shutil.copyfile(path, raw / f"{path.parent.name}.json")
    (into / "baselines.json").write_text(
        json.dumps(_baselines(), indent=2) + "\n", encoding="utf-8"
    )
    (into / "facts.json").write_text(
        json.dumps(_facts(), indent=2) + "\n", encoding="utf-8"
    )
    (into / "index.json").write_text(
        json.dumps(
            {
                "generated_by": "site/tools/build_fixtures.py",
                "note": (
                    "Real runs, not authored data. Regenerate with "
                    "`python3 site/tools/build_fixtures.py`. The only edit made "
                    "to a bundle is rewriting this machine's repository path to "
                    f"{PLACEHOLDER!r}."
                ),
                "fixtures": entries,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return entries


def _check() -> int:
    """Regenerate into a temporary directory and diff what should not move."""
    if not (OUT / "index.json").exists():
        print("No fixtures committed yet. Run without --check first.")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp)
        _build(fresh)

        drifted: list[str] = []
        for path in sorted(OUT.rglob("*.json")):
            rel = path.relative_to(OUT)
            other = fresh / rel
            if not other.exists():
                drifted.append(f"{rel}: no longer produced")
                continue
            a = _strip_volatile(json.loads(path.read_text(encoding="utf-8")))
            b = _strip_volatile(json.loads(other.read_text(encoding="utf-8")))
            if a != b:
                drifted.append(f"{rel}: differs")

    if drifted:
        print("Fixtures are stale. Regenerate them:")
        for line in drifted:
            print(f"  {line}")
        return 1

    print(f"Fixtures reproduce. {len(list(OUT.rglob('*.json')))} files checked.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Re-run and compare against what is committed, instead of rewriting it.",
    )
    args = parser.parse_args(argv)

    if args.check:
        return _check()

    if OUT.exists():
        shutil.rmtree(OUT)
    entries = _build(OUT)

    print(f"{'fixture':<20} {'verdict':<12} shows")
    print("-" * 78)
    for entry in entries:
        print(f"{entry['key']:<20} {entry['verdict']:<12} {entry['shows'][:44]}")
    print(f"\n{len(entries)} fixtures written to {OUT.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
