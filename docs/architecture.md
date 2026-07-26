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
  → evaluate deterministic assertions
  → reset services
  → verify seed-state digest
  → write evidence.json and report.md
```

The core has no knowledge of OpenClaw, Hermes, Codex, or a particular model
provider.

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

The MVP mail service keeps all data in memory. Future services can use an
isolated database or a wrapped upstream simulator as long as they preserve
snapshot and reset semantics.

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
- Reset verification.
- Explicit limitations.
- A digest over the complete unsigned evidence document.

The digest detects accidental or intentional changes but is not yet a
cryptographic signature tied to a release identity.

## Result semantics

- `PASS`: the subject completed and every assertion passed.
- `FAIL`: the subject completed but one or more assertions failed.
- `INCOMPLETE`: the subject errored, timed out, was terminated, or otherwise
  failed to finish—even if the observable assertions happened to pass.

An absent assertion suite also resolves to `INCOMPLETE`.

`INCOMPLETE` also covers the case where Beacon could not collect the evidence
it needed. A subject that finishes without producing the scenario's declared
artifact leaves the assertions reading that artifact with nothing to evaluate;
reporting `FAIL` would state a conclusion about the subject's behavior that was
never measured. The distinction is between *the subject did the wrong thing*
and *we do not know what the subject did*.

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

## Planned adapter convergence

MCP and A2A currently have protocol-inspection clients. The next architecture
increment should make both implement the `SubjectAdapter` contract:

```text
MCPScenarioAdapter
  → start/connect server
  → discover capabilities
  → execute scenario-declared tool calls or connect an agent host
  → normalize MCP requests, results, logging, and elicitation

A2AScenarioAdapter
  → discover Agent Card
  → submit scenario goal
  → stream task updates and artifacts
  → handle input-required and cancellation
  → normalize all A2A events
```

Native runtime adapters can add lifecycle, configuration, approval, token, and
cost evidence without changing scenario or evidence contracts.

