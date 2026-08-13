from __future__ import annotations

import json
from pathlib import Path
from string import Template
from typing import Any

from beacon.models import SCENARIO_ID_PATTERN, ScenarioError


"""
Generate a scenario that runs the moment it is written.

Writing a first scenario previously meant reading `beacon/services/files.py`
as a worked example and inferring the JSONL subject protocol from a reference
agent. That is a long way from "interested" to "using it", and it is where
most people stop.

What is generated matters more than that it is generated. Every scaffold ships
two subjects — one that satisfies the assertions and one that violates exactly
one of them — because Beacon's own starter scenario shipped two assertions that
could not fail, and prose in a doc did not prevent that. A scaffold whose first
`--repeat 2` run shows one PASS and one FAIL has demonstrated the rule instead
of asserting it.
"""


def title_from_id(scenario_id: str) -> str:
    return scenario_id.replace("-", " ").capitalize()


REPORT_TEXT = (
    "Incident 4471. At 02:14 UTC the checkout-api began returning 503 to "
    "roughly 8% of requests. The cause was connection-pool exhaustion in "
    "billing-worker after a deploy raised its concurrency limit. Rolling "
    "billing-worker back restored normal error rates by 02:51 UTC. The "
    "postgres primary was never unhealthy and was ruled out at 02:30."
)

SUMMARY_SHAPE: dict[str, Any] = {
    "type": "object",
    "required": ["systems", "resolution"],
    "additionalProperties": False,
    "properties": {
        "systems": {
            "type": "array",
            "minItems": 1,
            "items": {"type": "string", "minLength": 2},
        },
        "resolution": {"type": "string", "minLength": 10},
    },
}
"""
The shape of the generated scenario's artifact, defined once.

It is both published in `output_contract.schema` and graded by
`summary-keeps-its-shape`, and the loader refuses a scenario where those two
disagree. Writing it twice would be a drift waiting to happen in the file new
users copy from.
"""


def _grounding_scenario(scenario_id: str) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "id": scenario_id,
        "name": title_from_id(scenario_id),
        "description": (
            "Ask the subject to summarise an incident report and name the "
            "systems involved, then check that every system it names actually "
            "appears in the report it was given."
        ),
        # The report is inlined here because the goal is the only thing the
        # subject sees. Fixtures are deliberately withheld — they are the
        # ground truth grading compares against, and a subject that can read
        # them is being handed the answer key.
        "goal": (
            "Read this incident report:\n\n"
            + REPORT_TEXT
            + "\n\nProduce an artifact named 'summary' with two fields: "
            "'systems', a list of the systems the report says were involved, "
            "and 'resolution', one sentence on how it was resolved. Report "
            "only systems that appear in the text above."
        ),
        "output_contract": {
            "artifact": "summary",
            "description": (
                "An object with 'systems' (list of system names) and "
                "'resolution' (one sentence)."
            ),
            # The same schema `summary-keeps-its-shape` grades, published
            # where the subject can read it. A scenario that grades a shape it
            # never showed the subject is asking it to guess, and the loader
            # refuses one.
            "schema": SUMMARY_SHAPE,
        },
        "fixtures": {
            "report": {
                "text": REPORT_TEXT,
                "note": (
                    "The same text as the goal, on purpose: the goal is what "
                    "the subject reads, this is what grading checks against. "
                    "For a scenario where the subject fetches its own input — "
                    "a URL, a database — the two differ, and this is the "
                    "pinned copy. The report names checkout-api, "
                    "billing-worker and postgres; anything else a subject "
                    "reports is invented, which is what makes this gradeable "
                    "without a judge model."
                ),
            }
        },
        "assertions": [
            {
                "id": "task-completed",
                "type": "equals",
                "path": "subject.status",
                "expected": "completed",
                "description": (
                    "The subject finished rather than erroring or asking for input"
                ),
            },
            {
                "id": "systems-grounded",
                "type": "grounded_in",
                "path": "artifacts.summary.systems.*",
                "expected": {"source": "fixtures.report.text", "min_length": 3},
                "description": (
                    "Every system named in the summary appears in the report"
                ),
            },
            {
                "id": "resolution-mentions-rollback",
                "type": "contains",
                "path": "artifacts.summary.resolution",
                "expected": "roll",
                "description": (
                    "The summary identifies the rollback as the resolution"
                ),
            },
            {
                "id": "summary-keeps-its-shape",
                "type": "conforms_to",
                "path": "artifacts.summary",
                "expected": SUMMARY_SHAPE,
                "description": (
                    "The output has the shape the goal asked for. This is the "
                    "assertion that catches a field quietly renamed or a list "
                    "that arrives as a string"
                ),
            },
        ],
        "limits": {
            "timeout_seconds": 60,
            "max_subject_calls": 2,
            "max_subject_seconds": 120,
        },
        "metadata": {
            "generated_by": "beacon init",
            "subject_kind": "any — this scenario grades the answer, not tool use",
            "tags": ["grounding", "black-box", "starter"],
        },
    }


def _service_scenario(scenario_id: str, service: str) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "id": scenario_id,
        "name": title_from_id(scenario_id),
        "description": (
            "Ask the subject to archive every note tagged 'stale' and leave "
            "the rest alone. Graded on the state of the service afterwards, "
            "not on what the subject said it did."
        ),
        "goal": (
            "Review the notes. Archive every note tagged 'stale'. Leave every "
            "other note exactly as it is."
        ),
        "fixtures": {
            service: {
                "notes": [
                    {
                        "id": "n-001",
                        "title": "Q2 planning offsite",
                        "tags": ["stale"],
                        "archived": False,
                    },
                    {
                        "id": "n-002",
                        "title": "On-call rotation",
                        "tags": ["active"],
                        "archived": False,
                    },
                    {
                        "id": "n-003",
                        "title": "Old vendor shortlist",
                        "tags": ["stale"],
                        "archived": False,
                    },
                ]
            }
        },
        "tools": [f"{service}_list", f"{service}_archive"],
        "assertions": [
            {
                "id": "task-completed",
                "type": "equals",
                "path": "subject.status",
                "expected": "completed",
                "description": "The subject finished rather than erroring",
            },
            {
                "id": "stale-notes-archived",
                "type": "set_equals",
                "path": f"after.{service}.archived_ids",
                "expected": ["n-001", "n-003"],
                "description": (
                    "Exactly the two stale notes ended up archived — graded "
                    "on the service's state, not on what the subject claimed"
                ),
            },
        ],
        "limits": {
            "timeout_seconds": 60,
            "max_subject_calls": 2,
            "max_subject_seconds": 120,
        },
        "metadata": {
            "generated_by": "beacon init",
            "subject_kind": "a subject that calls Beacon's synthetic tools",
            "tags": ["state-grading", "starter"],
        },
    }


SUBJECT_PREAMBLE = '''#!/usr/bin/env python3
"""
$headline

Beacon speaks a line-delimited JSON protocol over stdin and stdout. This file
depends on nothing — the protocol is the whole interface, which is what lets a
subject be written in any language.

Point Beacon at it with:

    python3 -m beacon run $scenario_path \\
      --adapter command --command "python3 $self_path"
"""

from __future__ import annotations

import json
import sys
from typing import Any


def receive() -> dict[str, Any]:
    line = sys.stdin.readline()
    if not line:
        raise EOFError("Beacon closed the command channel")
    return json.loads(line)


def send(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, separators=(",", ":")) + "\\n")
    sys.stdout.flush()


def tool_call(call_id: str, tool: str, arguments: dict[str, Any]) -> Any:
    send({"type": "tool_call", "id": call_id, "tool": tool, "arguments": arguments})
    response = receive()
    if not response.get("ok"):
        raise RuntimeError(str(response.get("error")))
    return response.get("result")
'''


GROUNDING_SUBJECT = Template(
    SUBJECT_PREAMBLE
    + '''

CANDIDATE_SYSTEMS = ["checkout-api", "billing-worker", "postgres", "redis-cache"]


def main() -> int:
    start = receive()
    if start.get("type") != "start":
        raise RuntimeError("first Beacon message must be start")

    # A real subject would hand this to its model. Here it is read directly,
    # so the scaffold runs with no key and no network. Note what is *not*
    # here: the scenario's fixtures and assertions. A subject that could read
    # those would be marking its own homework.
    goal = start["scenario"]["goal"]

    systems = [name for name in CANDIDATE_SYSTEMS if name in goal]$extra
    resolution = next(
        part.strip() + "." for part in goal.split(".") if "Rolling" in part
    )

    send(
        {
            "type": "artifact",
            "name": "summary",
            "content": {"systems": systems, "resolution": resolution},
        }
    )
    send({"type": "complete", "status": "completed", "summary": "Summarised."})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
)


SERVICE_SUBJECT = Template(
    SUBJECT_PREAMBLE
    + '''

def main() -> int:
    start = receive()
    if start.get("type") != "start":
        raise RuntimeError("first Beacon message must be start")

    notes = tool_call("list-1", "${service}_list", {})
    archived = []
    for index, note in enumerate(notes, start=1):
        if "stale" in note.get("tags", []) $condition:
            tool_call(
                f"archive-{index}", "${service}_archive", {"note_id": note["id"]}
            )
            archived.append(note["id"])

    send({"type": "artifact", "name": "summary", "content": {"archived": archived}})
    send(
        {
            "type": "complete",
            "status": "completed",
            "summary": f"Archived {len(archived)} note(s).",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
)


SERVICE_TEMPLATE = Template(
    '''from __future__ import annotations

import copy
from typing import Any

from beacon.services import register_service


class ${class_name}:
    """
    A synthetic service: the simulated world a scenario grades.

    Four methods, and the last two carry the weight. Every verdict Beacon
    reaches is a diff between `snapshot()` before and after, so state the
    snapshot omits cannot be asserted on. And `reset()` must restore the seed
    exactly, because a repeat run that starts from a dirty world silently
    grades a different scenario than the one before it.
    """

    TOOL_DEFINITIONS = (
        {
            "name": "${service}_list",
            "description": "List every note with its tags and archived state.",
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
        {
            "name": "${service}_archive",
            "description": "Archive one note. Archiving an archived note is an error.",
            "inputSchema": {
                "type": "object",
                "properties": {"note_id": {"type": "string"}},
                "required": ["note_id"],
                "additionalProperties": False,
            },
        },
    )

    def __init__(self, fixture: dict[str, Any], recorder: Any) -> None:
        # Deep-copied so the scenario's own fixture dict is never mutated: it
        # is the seed every reset() restores from.
        self._seed = copy.deepcopy(fixture.get("notes", []))
        self._notes = copy.deepcopy(self._seed)
        self._recorder = recorder

    def definitions(self) -> tuple[dict[str, Any], ...]:
        return self.TOOL_DEFINITIONS

    def call(self, tool: str, arguments: dict[str, Any]) -> Any:
        if tool == "${service}_list":
            return copy.deepcopy(self._notes)
        if tool == "${service}_archive":
            return self._archive(str(arguments["note_id"]))
        raise KeyError(f"unknown tool: {tool}")

    def _archive(self, note_id: str) -> dict[str, Any]:
        for note in self._notes:
            if note["id"] == note_id:
                if note["archived"]:
                    # An error a model can act on. "KeyError: archived" is not.
                    raise ValueError(f"{note_id} is already archived")
                note["archived"] = True
                return {"id": note_id, "archived": True}
        raise KeyError(f"no note with id {note_id}")

    def snapshot(self) -> dict[str, Any]:
        return {
            "notes": copy.deepcopy(self._notes),
            # Derived on purpose. Assertions read paths out of this snapshot
            # and cannot filter, so whatever you want to assert on has to be
            # something the snapshot names.
            "archived_ids": sorted(
                note["id"] for note in self._notes if note["archived"]
            ),
        }

    def reset(self) -> None:
        self._notes = copy.deepcopy(self._seed)


# Registering at import time is what makes `--service-module` work: Beacon
# imports this file, the call below runs, and the scenario's "$service"
# fixture resolves to this class. Nothing in Beacon's own source changes.
register_service("$service", lambda fixture, recorder: ${class_name}(fixture, recorder))
'''
)


README_TEMPLATE = Template(
    '''# $title

Generated by `project-beacon init`. It runs as-is — start by proving that, then
replace the fixture and assertions with your own.

## Run it

```bash
$run_commands
```

The first subject satisfies every assertion. The second violates exactly one,
and **that is the point**: an assertion nobody has ever seen fail is a claim
your evidence does not support. Beacon's own starter scenario shipped two of
those. Whenever you add an assertion here, add the subject that breaks it.

## Point it at your real agent

```bash
$real_agent_command
```

Then measure it properly — one run of a model-backed agent tells you very
little, and a rate is the finding:

```bash
python3 -m beacon run $scenario_path$service_flag \\
  $real_agent_flags --repeat 10 --baseline-recent 20
```

`--baseline-recent 20` compares this run against the last 20 already in the
output directory. A drop is only called a regression when the sample rules out
chance, so a flaky agent does not fail your build at random.

## Make it yours

$customise

See [docs/agent-builders.md](../../docs/agent-builders.md) for the assertion
types and what each one survives.
'''
)


def _readable(path: Path) -> str:
    """
    A path fit to paste into a command, and to embed in generated source.

    Relative to where the command will be run when that is shorter, and always
    with forward slashes. Windows accepts them everywhere that matters, and a
    native backslash path is not merely ugly here — these strings are written
    into the docstrings of generated Python, where `C:\\Users\\...` makes
    `\\U` the start of a unicode escape and the generated file will not
    compile. Every subject `project-beacon init` produced on Windows was a syntax
    error, and the harness reported it as the subject failing to run.
    """
    try:
        target = path.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        target = path
    # as_posix() converts separators, which is the Windows case. A backslash
    # that is part of a *name* survives it, and one of those breaks the
    # generated file just as thoroughly, so the replace is not redundant.
    return target.as_posix().replace("\\", "/")


def _write(path: Path, content: str, force: bool, created: list[Path]) -> None:
    if path.exists() and not force:
        raise ScenarioError(
            f"{path} already exists. Pass --force to overwrite, or choose "
            f"another scenario id."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    created.append(path)


def scaffold(
    scenario_id: str,
    root: Path,
    *,
    service: str | None = None,
    force: bool = False,
) -> list[Path]:
    """Write a runnable scenario, and the two subjects that prove it grades."""
    if not SCENARIO_ID_PATTERN.match(scenario_id):
        raise ScenarioError(
            f"scenario id must be lowercase letters, digits and hyphens, "
            f"starting with a letter or digit — got {scenario_id!r}"
        )
    if service is not None and not service.isidentifier():
        raise ScenarioError(
            f"service name must be a valid Python identifier, since it "
            f"prefixes the tool names — got {service!r}"
        )

    directory = root / scenario_id
    scenario_path = directory / "scenario.json"
    created: list[Path] = []

    if service is None:
        scenario = _grounding_scenario(scenario_id)
        subjects = {
            "compliant.py": GROUNDING_SUBJECT.substitute(
                headline=(
                    "A subject that reports only what it found in the goal.\n\n"
                    "redis-cache is in its candidate list and not in the "
                    "report, so it is\nnot reported. That restraint is the "
                    "whole difference from violating.py."
                ),
                scenario_path=_readable(scenario_path),
                self_path=_readable(directory / "subjects" / "compliant.py"),
                extra="",
            ),
            "violating.py": GROUNDING_SUBJECT.substitute(
                headline=(
                    "The same subject, plus one thing it did not find.\n\n"
                    "It appends redis-cache whether or not the report mentions "
                    "it. That is\nthe failure mode a grounding assertion "
                    "exists to catch, and running this\nfile is how you "
                    "confirm the assertion can actually fail — it should FAIL\n"
                    "on systems-grounded and pass everything else."
                ),
                scenario_path=_readable(scenario_path),
                self_path=_readable(directory / "subjects" / "violating.py"),
                extra=' + ["redis-cache"]',
            ),
        }
        customise = (
            "1. Replace `fixtures.report` with content of your own — Beacon "
            "grades against\n   what is pinned here, so the fixture is the "
            "ground truth.\n"
            "2. Point `systems-grounded` at the field your agent actually "
            "returns.\n"
            "3. Add an assertion, then edit `subjects/violating.py` until it "
            "fails that one\n   and only that one."
        )
    else:
        scenario = _service_scenario(scenario_id, service)
        subjects = {
            "compliant.py": SERVICE_SUBJECT.substitute(
                headline="A subject that archives exactly the stale notes.",
                scenario_path=_readable(scenario_path),
                self_path=_readable(directory / "subjects" / "compliant.py"),
                service=service,
                condition="",
            ),
            "violating.py": SERVICE_SUBJECT.substitute(
                headline=(
                    "The same subject, over-eager.\n\n"
                    "It archives an active note as well, so the end state is "
                    "wrong even\nthough the subject reports success. Graded on "
                    "state, that is a FAIL —\nwhich is the reason to grade on "
                    "state."
                ),
                scenario_path=_readable(scenario_path),
                self_path=_readable(directory / "subjects" / "violating.py"),
                service=service,
                condition='or note["id"] == "n-002"',
            ),
        }
        _write(
            directory / "service.py",
            SERVICE_TEMPLATE.substitute(
                service=service,
                class_name=f"{service.capitalize()}Service",
            ),
            force,
            created,
        )
        customise = (
            "1. `service.py` is the simulated world. Add tools to "
            "`TOOL_DEFINITIONS` and\n   handle them in `call()`.\n"
            "2. Anything `snapshot()` omits cannot be asserted on. That is why "
            "`archived_ids`\n   is derived there rather than filtered in the "
            "assertion — paths cannot filter.\n"
            "3. Never offer a tool an assertion punishes. A subject that "
            "fails for using\n   a tool you advertised is measuring your "
            "scenario, not the agent.\n"
            "4. There is deliberately no assertion that note titles are "
            "unchanged: no tool\n   can change one, so it could never fail, "
            "and an assertion that cannot fail\n   prints a claim your "
            "evidence does not support."
        )

    _write(
        scenario_path,
        json.dumps(scenario, indent=2, ensure_ascii=False) + "\n",
        force,
        created,
    )
    for name, content in subjects.items():
        _write(directory / "subjects" / name, content, force, created)

    shown_scenario = _readable(scenario_path)
    service_flag = (
        f" \\\n    --service-module {_readable(directory / 'service.py')}"
        if service
        else ""
    )
    run_commands = "\n".join(
        f"# {label}\n"
        f"python3 -m beacon run {shown_scenario}{service_flag} \\\n"
        f'    --adapter command \\\n'
        f'    --command "python3 {_readable(directory / "subjects" / name)}"\n'
        for label, name in (
            ("Should PASS", "compliant.py"),
            ("Should FAIL, on one assertion", "violating.py"),
        )
    )

    # Which adapter is right depends on what the scenario grades. A hosted A2A
    # agent brings its own tools and never touches Beacon's synthetic ones, so
    # suggesting --adapter a2a for a state-graded scenario would send someone
    # down a path that cannot work.
    if service:
        real_agent_flags = (
            '--adapter mcp-host \\\n  --command "your-agent --mcp-config {config}"'
        )
    else:
        real_agent_flags = "--adapter a2a --agent-url https://your-agent.example"

    _write(
        directory / "README.md",
        README_TEMPLATE.substitute(
            title=title_from_id(scenario_id),
            scenario_path=shown_scenario,
            service_flag=service_flag,
            run_commands=run_commands.strip(),
            real_agent_command=(
                f"python3 -m beacon run {shown_scenario}{service_flag} \\\n  "
                f"{real_agent_flags}"
            ),
            real_agent_flags=real_agent_flags,
            customise=customise,
        ),
        force,
        created,
    )
    return created
