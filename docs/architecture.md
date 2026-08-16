# MVP architecture

## Core lifecycle

```text
Scenario
  → prepare synthetic services
  → capture before-state digest
  → start subject adapter
  → route and record tool calls
  → capture artifacts and events
  → capture after-state digest
  → run any repeat passes the scenario declared, each with fresh services
  → evaluate deterministic assertions
  → reset services
  → verify seed-state digest
  → write evidence.json and report.md
```

The core has no knowledge of OpenClaw, Hermes, Codex, or a particular model
provider.

## Where the pieces live

```text
beacon/models.py       Scenario, AssertionSpec, Evidence — the published contracts
beacon/assertions.py   Every assertion type: what each requires, and how it grades
beacon/evaluation.py   Dispatch, the measured/unmeasured rule, and the verdict
beacon/runner.py       The lifecycle above, including any repeat passes
beacon/services/       The six services, the tool router, faults, descriptions
beacon/taxonomy.py     The failure taxonomy and the computed coverage figure
```

The split between the last two of the first three is the one worth knowing
about. `assertions.py` holds a `REGISTRY` of eighteen types; each handler
returns `(passed, actual, expected, message)` and raises `EvaluationError` for
anything it cannot read. It never builds a result and never sets `measured`.
`evaluation.py` does both, in one place, which is why an unreadable path
becomes "we could not tell" rather than "the subject did the wrong thing" no
matter which type produced it. `models.ASSERTION_TYPES` is a view over that
registry rather than a second copy, so a registered type is loadable by
construction.

## Main contracts

### Scenario

A scenario declares:

- The outcome-oriented goal.
- Synthetic service fixtures.
- The tool surface exposed to the subject.
- The output contract the subject must satisfy.
- Required and forbidden observable behavior.
- Resource limits.
- Author, provenance, rights, and classification metadata.

The versioned JSON Schema is in `schemas/scenario.schema.json`.

Two of those exist to keep the scenario honest with the subject.

`tools` scopes what the subject is offered. A scenario forbids an action by not
offering it, never by offering a tool an assertion punishes: a subject cannot
be expected to infer that an advertised capability is a trap. Tools that are
deliberately available-but-forbidden — the ones a forbidden-action assertion
watches for — stay in the surface, because the assertion is only meaningful if
the attempt is possible. A scoped name no registered service provides is a
scenario error.

`output_contract` names the artifact the subject must return, and is published
in the `start` message. Assertions are not: a subject that can read its own
grading criteria is not being evaluated. Anything the subject is *required* to
do therefore belongs in the output contract, or it is a hidden requirement it
cannot satisfy.

That rule is now enforced rather than merely stated. A scenario grading the
shape of the contracted artifact must publish that shape in
`output_contract.schema`, and the loader refuses one where the published and
graded schemas disagree. Three shipped scenarios and the output of `beacon
init` broke this: `web-extraction-contract` and `web-extraction-grounding`
demanded six named fields while the contract said only "Structured extraction
of the page at the URL in the goal". The shape was one hosted agent's native
output format, so those scenarios could grade that agent and nothing else —
which is not a scenario, it is a fixture with an audience of one.

### Subject adapter

Every subject adapter exposes:

```python
@property
def descriptor(self) -> dict: ...

def execute(self, context: ExecutionContext) -> SubjectResult: ...
```

The descriptor records the subject identity, adapter type, version, and
integration level. `execute` receives only the prepared scenario context,
scoped tools, event recorder, run directory, and artifact collector.

Runtime-specific metadata belongs in the descriptor or normalized events, not
in the scenario schema.

### Synthetic service

A service supplies:

- Machine-readable tool definitions.
- A deterministic call implementation.
- A complete state snapshot.
- An exact reset operation.

Two optional helpers are composed by every shipped service rather than
inherited. `FaultTable` (`beacon/services/faults.py`) reads a `faults` key from
the fixture and makes a named call fail on demand, including
`after_effect: "applied"` — the call that errors *after* taking effect.
`DescriptionTable` (`beacon/services/descriptions.py`) lets the fixture write a
tool's own description, which is the only channel into an agent that arrives
from its own harness. Both record an event when they fire, so a scenario can
assert the mechanism was actually exercised rather than assuming it was; the
taxonomy declares each as a capability that specific cells require.

That contract is `beacon.services.SyntheticService`, and services are built
from a registry keyed by fixture name rather than from a branch in the runner:

```python
from beacon.services import register_service
register_service("calendar", CalendarService)
```

Registration is public, so a scenario pack can ship its own service and
register it on import without editing anything in `beacon/`. A fixture with no
registered service is plain data — a pinned source document a black-box
scenario compares claims against — not an error.

Beacon ships six, all in memory: `files`, `mail`, `web`, `tickets`, `shell`
and `payments`. A future service can use an isolated database or wrap an
upstream simulator as long as snapshot and reset stay exact: every verdict is a
diff between two snapshots, and a reset that is not exact corrupts the next run
of a repeat.

### Evidence

Evidence contains:

- Scenario and subject identity.
- Subject completion status.
- PASS, FAIL, or INCOMPLETE result.
- Individual assertion results.
- Before and after state with SHA-256 digests.
- Canonical state changes.
- Ordered events.
- Produced artifacts.
- Measured token and call usage, and whether any of it was self-reported.
- Later repeat passes, when the scenario declared `repeat`: their artifacts,
  end state and ending, but never their events, so every other assertion still
  reads exactly one run.
- Reset verification.
- Explicit limitations.
- A digest over the complete unsigned evidence document.

The bundle is stamped `evidence_version`, currently `0.4`, and
`schemas/evidence.schema.json` is the published contract for it.

The digest detects accidental or intentional changes but is not yet a
cryptographic signature tied to a release identity.

## Result semantics

- `PASS`: the subject reached an ending it chose, and every assertion passed.
- `FAIL`: at least one assertion Beacon could measure did not pass.
- `INCOMPLETE`: the subject errored, timed out, was terminated, or otherwise
  failed to reach an ending of its own — even if the observable assertions
  happened to pass.

"An ending it chose" is `completed`, `input_required` or `declined`
(`INTENTIONAL_ENDINGS` in `beacon/models.py`). Stopping to ask a human is a
decision, not a crash, so a scenario states the ending it expects with an
assertion on `subject.status` and grades that like anything else. What stops a
subject passing everything by escalating from every task is that the assertion
is there and can fail.

`FAIL` outranks a gap. A measured failure is a finding, and a finding outranks
"we could not tell": a subject that abandoned its output contract failed
`conforms_to` outright while every sibling assertion reading a field of the
object it never produced came back unmeasured, and the run used to report
INCOMPLETE about something Beacon could describe exactly.

An absent assertion suite resolves to `INCOMPLETE`.

`INCOMPLETE` also covers the case where Beacon could not collect the evidence
it needed. A subject that finishes without producing the scenario's declared
artifact leaves the assertions reading that artifact with nothing to evaluate;
reporting `FAIL` would state a conclusion about the subject's behavior that was
never measured. The distinction is between *the subject did the wrong thing*
and *we do not know what the subject did*.

That applies to a path inside the artifact as much as to the artifact itself.
An assertion whose path cannot be reached is recorded with `measured: false`
and prints as `NOT MEASURED` rather than `FAIL`. On its own it resolves the run
to `INCOMPLETE`; beside a measured failure it does not soften it. This was a
`FAIL` until a real model returned prose where a
scenario expected `primary_entities[].value`, and the report announced "Every
entity the agent reports appears in the page it was given: FAILED" about a
comparison that never ran. An authoring mistake that makes an assertion
unevaluable is treated the same way, because it is not the subject
misbehaving either.

Symmetrically, a completion that was validly reported is not retracted by what
happens during teardown. A subject that sends `complete` and then exits
non-zero, or takes longer than the teardown budget to shut down, has finished
its work; the exit status is recorded as an event rather than converted into a
verdict.

## Isolation boundary

The current external-command adapter:

- Uses a fresh run working directory.
- Passes a small allowlist of environment variables.
- Enforces the wall-clock timeout the scenario declares.
- Enforces the maximum protocol-message count the scenario declares.
- Terminates and then kills an unresponsive process.

Budgets come from the scenario, not from the adapter's defaults. An operator
override is applied but recorded against the declared value, because a
scenario that publishes one limit into its evidence and runs under another is
misleading about the conditions of the run.

This does not prevent a malicious process from accessing other host resources
available to the current user. Hardened container/VM isolation, per-run network
policy, filesystem mounts, cgroups/resource limits, and secret scanning remain
required before running untrusted subjects.

## MCP: two channels, not one

Beacon both consumes and serves MCP, and the two do different jobs.

The **client** (`project-beacon mcp-inspect`) connects to someone else's server. It
grades a tool provider, not an agent.

The **façade** (`ScenarioMCPServer`) serves the scenario's own tool surface, so
an MCP-speaking agent host becomes the subject. Calls route through the same
`ToolRouter` as every other adapter, which is what keeps the evidence identical
in shape: the same events, the same scoping, the same argument validation, the
same policy enforcement, the same state snapshots.

The façade alone cannot produce a verdict. MCP has no completion signal, so a
client that disconnects is indistinguishable from one that crashed, and
`subject_status` is the only input to the result. Two things resolve that:

- **`beacon_submit`**, an ordinary tool on the façade that the goal tells the
  subject to call last. It carries the status, the summary, and the artifact
  the output contract asks for. A session that ends without it is INCOMPLETE —
  the honest answer when Beacon cannot tell whether the work finished.
- **A lifecycle owner.** `MCPHostAdapter` starts the façade, launches the host,
  and owns start, timeout and termination. `MCPServeAdapter` skips the launch
  and waits for a host you connect yourself, at the cost of not being able to
  see it start.

The transport is HTTP on loopback with a per-run bearer token, not stdio. Over
stdio the host spawns the server as its own child, so Beacon would neither own
the service state nor outlive the connection.

Tool names must match `^[a-zA-Z0-9_-]{1,64}$`, checked when a service
registers. Every surface that publishes a tool set to a model applies that
constraint, so a name that violates it fails at the provider boundary rather
than producing a verdict.

There is a third MCP shape that is neither of those. `MCPToolSubjectAdapter`
points Beacon *at* a hosted server and grades one of its tools as the subject:
Beacon is the client rather than the server, the tool call is the whole of the
run, and the integration level is 1 because nothing about the agent behind the
tool is observable. It is how twenty-nine hosted agents were probed.

`beacon adapters` prints the full table with each one's integration level,
probed from the adapter's own descriptor rather than declared.

## Still planned

`A2ASubjectAdapter` ships and is reachable as `beacon run --adapter a2a`: it
discovers the Agent Card at both well-known paths, submits the goal, accepts a
reply as either a Task or a bare Message, and treats `input-required` as an
ending the subject chose. What remains unimplemented is streaming task updates
and cancellation, so a long-running A2A agent is graded on its final reply
rather than watched.

Native runtime adapters can add lifecycle, configuration, approval, token, and
cost evidence without changing scenario or evidence contracts.

