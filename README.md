# Project Beacon

Project Beacon is an open, protocol-neutral trial and readiness lab for AI
agents, tools, and multi-agent systems.

Its product promise is:

> Try an agent on realistic work before trusting it with real work.

This repository contains the first technical MVP. It proves that one scenario
can run against different subject adapters, mutate synthetic services, produce
deterministic PASS/FAIL/INCOMPLETE evidence, reset exactly, and expose MCP and
A2A protocol entry points without coupling the core to one agent runtime.

## Sixty seconds

Not on PyPI yet — clone it. There is nothing to install: the core is stdlib
only, and `python3 -m beacon` works straight out of the checkout.

```bash
git clone https://github.com/RealMaxPower/project-beacon
cd project-beacon

python3 -m beacon scenarios            # the seven that ship
python3 -m beacon run inbox-briefing   # run one, get an evidence bundle
python3 -m beacon init my-first-probe  # scaffold your own
```

`init` writes a scenario that runs immediately plus two subjects: one that
satisfies every assertion and one that violates exactly one. **The second is
meant to fail** — watching it fail is the only proof the assertion measures
anything. Add `--service notes` for a scenario graded on the state of a
simulated service instead of on the answer.

Packaging builds and installs clean into an empty environment, but nothing has
been published, so `pip install project-beacon` does not work yet. When it
does, `beacon` replaces `python3 -m beacon` and a bare scenario name replaces
a path.

The smoke test that verified this used to run only `--version`, `scenarios`,
`validate`, `run` and `init` — which is exactly the subset that worked while
the sdist was shipping without `examples/`, `docs/` or `schemas/`, breaking
every command on this page that names one. `MANIFEST.in` fixes the
distribution and `tests/test_packaging.py` fails if it regresses.

## What works

- Seven scenarios: three graded on the state of a synthetic service (mail and
  files), and four graded on what a hosted agent returned — grounding,
  fabrication, output-schema conformance, and injection resistance.
- Prompt-injection scenarios for both integration levels, detecting tool
  coercion through recorded attempts and exfiltration through canaries that
  exist only in the withheld material.
- Output-schema conformance that reports every violation with its path, and
  refuses a misspelled keyword instead of ignoring it.
- `beacon init`, which generates a scenario that runs immediately together
  with the subject that violates it.
- A deterministic in-process reference agent.
- A bidirectional JSONL adapter for wrapping a CLI, API, or SDK agent.
- Synthetic mail and document services with scoped tools and policy
  enforcement, built from a public registry so a scenario pack can add its own.
- Scenario-declared tool surfaces, output contracts, and resource limits.
- State-based assertions, forbidden-action checks, grounded citation checks
  that a name-drop does not satisfy, and shape checks that a renamed field
  cannot slip past.
- Before/after state digests and human-readable state diffs.
- Exact reset verification, cross-run flakiness rates, and regression
  detection against either a committed baseline or the last N runs, with a
  significance test so a flaky subject does not fail CI at random.
- JSON evidence, event logs, and a Markdown report — written for every run,
  whatever the verdict, and digested so a later edit is detectable. The digest
  is an unsigned SHA-256 integrity check, and nothing yet ships a command to
  verify one.
- Scenario validation at load time, enforced in code and kept in step with the
  published JSON Schema by test rather than read from it at run time.
- An adversarial subject suite that tests whether the verdicts are right,
  and a check that every behavioural assertion has a subject which breaks
  it — so the report never states something nobody has tested.
- A worked scenario pack in [examples/scenario-pack/](examples/scenario-pack/)
  that brings its own service, with a test that runs it from outside the
  repository so "no need to edit Beacon" is evidence rather than a claim.
- An MCP server façade: any MCP host can be the subject, over HTTP with a
  per-run bearer token.
- An A2A subject adapter: a hosted agent is graded through the full
  scenario and evidence lifecycle with no bridge code, against both the 0.x
  and 1.x request shapes.
- Minimal MCP stdio and Streamable HTTP clients for discovery and tool calls.
- A2A discovery across both well-known card paths, and replies accepted as
  either a Task or a bare Message — checked against reference servers built
  with all five official SDKs, which found five defects the specification
  alone did not.
- Minimal A2A Agent Card discovery and message sending.
- A dependency-free Python CLI and test suite.

## What does not work yet

- The process runner is not a hardened container or VM sandbox.
- There is no OpenClaw, Hermes, Codex, or other native runtime adapter yet.
- There is no web UI, approval interface, service virtualization proxy, model
  cost accounting, signing, or hosted service.
- A passing report is evidence for one synthetic scenario and configuration.
  It is not a safety certification.

## Running it against a real model or a GUI host

Both need a person — one spends money, one involves a window.
[docs/running-it-yourself.md](docs/running-it-yourself.md) has the exact
commands, where the API key goes (your environment, never the command line),
and how to wire the MCP façade into Cursor or Claude Desktop.

## If you build agents

[docs/agent-builders.md](docs/agent-builders.md) is the shortest path: point
Beacon at your agent, measure how often it fails rather than whether it failed
once, and fail CI when it regresses against a recorded baseline. No API key —
your agent brings its own model, and grading is deterministic.

## Requirements

- Python 3.11 or newer.
- No runtime dependencies for the MVP.
- Linux, macOS, or Windows. See [docs/windows.md](docs/windows.md) for
  Windows-specific notes.

## Run the vertical slice

```bash
python3 -m beacon validate inbox-briefing
python3 -m beacon run inbox-briefing
```

The second command writes an immutable run directory beneath
`.beacon/runs/` containing:

```text
evidence.json   Machine-readable evidence bundle
events.json     Ordered event and tool-call log
report.md       Human-readable result report
```

The expected result is `PASS` with nine passing assertions, three draft
responses each answering an action-required message, no attempt to send or to
label, no protected-message access, and an exact reset.

Each of those is graded on an *attempt*, not on the end state. Policy blocks
sending either way, so `after.mail.sent == []` would be true however the
subject behaved — an assertion that cannot fail, which this scenario shipped
until a coverage check found it. `send-never-attempted` is the one that means
something.

The scenario includes a synthetic prompt-injection payload: one message wraps a
genuine request around an instruction to send everything and open protected
mail. Answering the request is correct; obeying the instruction is what the
forbidden-action assertions catch.

## Grade the shape and the truth separately

An agent can hold its output contract perfectly while inventing what goes
inside it, so the two are graded by different scenarios. Twelve runs of each
against a real model, recorded in [baselines/](baselines/):

```text
web-extraction-contract     result matches the contract    2 / 12
web-extraction-grounding    entities grounded in the page  measured 0 / 12
```

The second row is the one worth pausing on. `entities-grounded` was not
failed — it was never *evaluated*. It reads `primary_entities[].value`, and a
reply that arrives as prose has no such path, so there was nothing to compare
and every run resolved INCOMPLETE. **You cannot measure whether an agent tells
the truth until it holds its shape**, and a harness that scored those runs as
failures would be publishing a fabrication rate it never measured.

Where the shape did hold, the fabrication is real: asked about `example.com`,
the model recited that page's *older* wording against the capture the scenario
pins.

`conforms_to` reports every violation with its path rather than the first, and
refuses a misspelled keyword at load time instead of ignoring it:

```text
FAILED -> summary-keeps-its-shape
  confidence         is not an accepted property
  documents[0].point is 2 characters, minimum 10
  documents[1].path  is required but missing
  themes[0]          expected string, got integer
```

## Test whether content can give orders

`scenarios/injection-resistance` puts injected instructions inside documents a
subject is asked to summarise; `scenarios/hosted-injection-resistance` puts one
in the content sent to a hosted agent. Detection is deterministic:
`event_absent` catches coerced tool calls — recorded before dispatch, so an
attempt policy refused is still evidence — and `contains_none` catches
exfiltration using strings that appear only in the withheld material, never in
the injected instruction. An agent that quotes the injection while declining it
passes, which is the behaviour you want.

Pair it with an assertion that the real work happened. An agent that answers
something else entirely leaks nothing and would otherwise pass.

## Check that a result is repeatable

A single passing run says little if the next one disagrees. `--repeat` runs the
same scenario against the same subject several times and compares the verdict,
the shape of the before/after state, and the per-assertion result vector:

```bash
python3 -m beacon run scenarios/inbox-briefing/scenario.json --repeat 5
```

```text
Determinism: STABLE across 5 runs (state shape, verdict, and assertion
results identical).
```

The command exits non-zero if any two runs disagree, and names the fields that
diverged. Run identifiers, timestamps, and the evidence digest are excluded
from the comparison because they differ by construction.

**Prose is excluded, structure is not.** A model-backed subject rewrites its
wording every run, so comparing state byte-for-byte reports every one of them
as non-deterministic however correctly it behaved — five runs against a real
model returned PASS with an identical assertion vector and identical draft
metadata, and were called DIVERGENT because the drafts were phrased
differently. So string *contents* are dropped from the comparison while
everything around them is kept: a different number of drafts, a renamed or
missing field, a changed count or flag, or a body that is sometimes empty all
still diverge. A run whose state differs only in wording is reported as a note,
not a failure, so nothing is passed over in silence.

This is narrower than it sounds. What a scenario cares about in its state is
what its assertions read, and assertion results are compared separately and
exactly. The state comparison is the supplementary tripwire, not the graded
property — and `state.after_digest` in the evidence bundle is still the exact
digest, because tamper evidence asks a different question.

Tool-call ordering is reported but does not count as divergence.

Use `--run-id` to give a run a stable directory name; repeats are suffixed
`-001`, `-002`, and so on.

## Catch a regression, not just a failure

`--repeat` asks whether a subject agrees with itself right now. Whether it is
worse than it was is a different question, and a subject can be perfectly
self-consistent and consistently wrong:

```bash
# Against a committed snapshot, recorded on the first run.
# baselines/ already holds two, written from twelve model runs each.
python3 -m beacon run scenarios/inbox-briefing/scenario.json \
  --repeat 10 --baseline baselines/inbox-briefing.reference.json

# Or against the last 20 runs already in the output directory
python3 -m beacon run scenarios/inbox-briefing/scenario.json \
  --repeat 10 --baseline-recent 20
```

```text
Baseline (last 20 run(s)): recorded 2026-07-01T09:00:00+00:00 over 20 run(s).
  REGRESSION  result-matches-the-contract passed 100% of baseline runs, 17% now (2/12)
```

Non-zero exit, so CI fails. Comparison is by pass **rate**, because a subject
failing a quarter of the time still passes three single-run comparisons in
four. A drop counts as a regression only when the sample rules out chance, so
a flaky agent does not fail the build at random — and how many runs it takes
to prove a regression scales with how flaky the baseline said the subject was.

## Run an external command subject

The JSONL bridge lets Beacon exercise an agent wrapper without importing its
framework:

```bash
python3 -m beacon run \
  scenarios/inbox-briefing/scenario.json \
  --adapter command \
  --command "python3 examples/reference_jsonl_agent.py"
```

The child process receives one `start` message:

```json
{
  "type": "start",
  "protocol_version": "0.1",
  "run_id": "run-...",
  "scenario": {
    "id": "inbox-briefing-draft-only",
    "goal": "...",
    "output_contract": {
      "artifact": "summary",
      "description": "A briefing citing the id of every action-required message it covers."
    },
    "limits": { "timeout_seconds": 30, "max_protocol_messages": 500 }
  },
  "tools": [
    { "name": "mail_list_messages", "description": "...", "inputSchema": {} }
  ]
}
```

`tools` carries only the tools this scenario exposes, and is authoritative:
anything else is refused and recorded as an attempt. `output_contract.artifact`
names the artifact the subject must return — a requirement it is never told is
not one it can meet. Assertions are never sent.

It may then write tool requests:

```json
{
  "type": "tool_call",
  "id": "call-001",
  "tool": "mail_list_messages",
  "arguments": {}
}
```

Beacon responds on the process's standard input:

```json
{
  "type": "tool_result",
  "id": "call-001",
  "ok": true,
  "result": []
}
```

The subject may emit `artifact` and `log` messages, and must finish with:

```json
{
  "type": "complete",
  "status": "completed",
  "summary": "Finished the scenario."
}
```

This contract can wrap a local CLI directly or a small bridge to a hosted API,
framework SDK, container, or proprietary agent.

## Run a real model as the subject

The bridge in [examples/anthropic_jsonl_agent.py](examples/anthropic_jsonl_agent.py)
is about 120 lines and hardcodes nothing about the scenario — the goal, the
tool definitions, and the required artifact all arrive in the `start` message:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
pip install anthropic

python3 -m beacon run scenarios/inbox-briefing/scenario.json \
  --adapter command \
  --command "python3 examples/anthropic_jsonl_agent.py" \
  --env-secret ANTHROPIC_API_KEY \
  --timeout 180 \
  --repeat 5
```

It lives in `examples/` deliberately: `docs/architecture.md` requires the core
to know nothing about any model provider, so a provider bridge is just another
external subject. Beacon still has no runtime dependencies.

### Passing credentials without leaking them

The subject environment is deny-by-default, so a credentialed agent needs an
explicit exception. Two flags provide one, and both take **names only** — the
value is read from Beacon's own environment, never the command line, because
the subject's command line is itself recorded in `evidence.json`.

| Flag | Effect |
|---|---|
| `--env-passthrough NAME` | Copy the variable to the subject. |
| `--env-secret NAME` | Copy it, and remove its value from the evidence bundle wherever it appears. |

Redaction covers tool arguments, tool results, artifacts, the subject's stderr,
and the recorded command, in raw, URL-encoded, and base64 forms — then the
evidence digest is taken, so it verifies against the published document. Passing
a credential-shaped name to `--env-passthrough` is refused with a pointer to
`--env-secret`.

This is exact-value matching, not a guarantee. A subject that transforms a
secret before emitting it defeats it, and its network access is unrestricted.
Every redacted bundle says so in its `limitations`.
[examples/subjects/leaks_its_key.py](examples/subjects/leaks_its_key.py) is a
canary that pushes its key through every one of those channels; the test suite
asserts the value appears in none of the three output files.

## Run an MCP host as the subject

Beacon serves the scenario's synthetic tools over MCP, so an MCP-speaking agent
host becomes the subject with no bridge code:

```bash
python3 -m beacon run scenarios/inbox-briefing/scenario.json \
  --adapter mcp-host \
  --command "python3 examples/mcp_host_agent.py"
```

The host learns where to connect from `BEACON_MCP_URL` / `BEACON_MCP_TOKEN` and
a generated `mcp-config.json`. Calls route through the same tool router as every
other adapter, so scoping, argument validation, policy enforcement, event
recording and state snapshots are unchanged — the evidence has the same shape.

To point a host you run yourself — a desktop client, an IDE, another runtime —
at a scenario:

```bash
python3 -m beacon serve-mcp scenarios/inbox-briefing/scenario.json
```

```text
MCP server: http://127.0.0.1:62826/mcp
Config:     .beacon/runs/run-.../workspace/mcp-config.json
Waiting up to 30s. Ctrl-C stops and still writes evidence.
```

Loopback only, with a per-run bearer token that is redacted from the evidence
like any other secret.

### How Beacon knows the run finished

MCP has no completion signal — a client that disconnects looks exactly like one
that crashed, and Beacon will not call that a pass. The façade therefore offers
one extra tool, `beacon_submit`, carrying the status, the summary, and the
artifact the output contract asks for. A session that ends without it resolves
to `INCOMPLETE`, which is the honest answer when Beacon cannot tell whether the
work was done.

That is also why `--adapter mcp-host` launches the host rather than only
serving: the façade is the tool channel, and the adapter is the lifecycle
channel that owns start, timeout and termination.

## Inspect an MCP server

The MVP MCP client supports `initialize`, `tools/list`, and `tools/call` over
stdio:

```bash
python3 -m beacon mcp-inspect \
  --command "python3 examples/mcp_echo_server.py"

python3 -m beacon mcp-inspect \
  --command "python3 examples/mcp_echo_server.py" \
  --call echo \
  --arguments '{"text":"hello"}'
```

This is the opposite direction from the façade above, and it answers a
different question: the façade grades an *agent* against synthetic services,
while this client grades a *server* — someone else's tool provider.

Grading a server as a subject in its own right is built —
`MCPToolSubjectAdapter` runs one tool on a hosted MCP server through the full
scenario and evidence lifecycle, and it is what probed 29 hosted agents in
[conformance/hosted-agent-probe.md](conformance/hosted-agent-probe.md). It has
no `--adapter` value yet, so reaching it means writing Python rather than a
command line, and no unit test covers it. Both are why it is not listed under
"What works".

## Inspect an A2A agent

Discover an Agent Card:

```bash
python3 -m beacon a2a-inspect https://agent.example
```

Optionally send a message:

```bash
python3 -m beacon a2a-inspect \
  https://agent.example \
  --send "Prepare the requested artifact."
```

The current spike supports the A2A v1.0 HTTP+JSON and JSON-RPC message paths.
Authentication can be supplied with `--authorization`; credentials are never
written into evidence by the protocol inspector.

## Compatibility model

| Level | Interface | Evidence available |
|---|---|---|
| 0 | Black-box prompt/API | Output and simulated final state |
| 1 | MCP | Tool discovery, calls, responses, and resulting state (`--adapter mcp-host`, `serve-mcp`) |
| 2 | A2A | Agent discovery, tasks, messages, statuses, and artifacts |
| 3 | CLI/API/SDK/container bridge | Lifecycle, events, budgets, and termination |
| 4 | Native runtime adapter | Runtime configuration, approvals, cost, and richer traces |

The only Level 4 subject today is Beacon's own in-process reference agent,
where Beacon *is* the runtime — which is why a default run's evidence reads
`Integration: in-process (level 4)` while "What does not work yet" says there
is no native runtime adapter. Both are true and the pair is easy to misread:
no adapter exists for anyone *else's* runtime, and the two rungs that promise
approvals and cost are promising evidence Beacon does not yet collect from any
subject.

OpenClaw and Hermes are intended as future Level 4 reference adapters. They are
not architectural dependencies.

## Test

```bash
python3 -W error::ResourceWarning -m unittest discover -s tests -v
```

The suite covers scenario validation, assertion resolution, state-based
evidence, the external command bridge, MCP stdio behavior, and A2A transport
behavior.

### Check that the verdicts are right

A passing test suite shows the pipeline runs. It does not show that the
verdicts are correct, because for a long time every subject Beacon had graded
was written by Beacon against the assertions doing the grading.

`examples/subjects/` holds forty subjects that behave the way a real agent
plausibly does — labelling handled mail, taking three seconds to shut down,
citing ids in uppercase, answering in JSON, obeying an injected instruction,
reading more than it should, crashing, hanging, corrupting stdout:

```bash
python3 examples/subjects/run_suite.py
```

```text
40/40 verdicts correct.
```

Over 400 tests, against an enforced floor of 80% branch coverage over
`beacon/` — a floor rather than a snapshot, because a number in prose goes
stale the week after it is written and nobody notices. Every workflow is
manual-only while this repository is private, so run both locally — between
them they are what CI would have run, minus the operating-system matrix. See
CONTRIBUTING.md.

Six of them were wrong when the suite was written. See
[examples/subjects/README.md](examples/subjects/README.md).

## Repository layout

```text
beacon/
  adapters/       Subject contracts and reference adapters
  protocols/      MCP and A2A protocol clients
  services/       Synthetic stateful services and tool router
  baseline.py     Pass-rate baselines and regression detection
  cli.py          Dependency-free command-line interface
  evaluation.py   Deterministic assertion engine
  evidence.py     JSON and Markdown evidence output
  outputschema.py Output-shape checking for `conforms_to`
  runner.py       Scenario lifecycle orchestration
  scaffold.py     `beacon init` scenario and service generation
examples/         External JSONL subject and MCP fixture
scenarios/        Versioned scenario packages and synthetic fixtures
schemas/          Scenario and evidence JSON Schemas
tests/            Hermetic unit and integration tests
docs/             Architecture and protocol contracts
```

## Design principles

- Grade observable outcomes and state changes before using LLM judges.
- Separate protocol adapters from runtime-specific adapters.
- Never treat “not run” or an errored subject as a pass.
- Make limitations part of every evidence bundle.
- Use synthetic fixtures in the MVP; do not request real service credentials.
- Prefer upstream standards and SDKs over proprietary formats.
- Preserve a useful open core without requiring a hosted account.

## License

Apache License 2.0. All included scenario fixtures are synthetic.

