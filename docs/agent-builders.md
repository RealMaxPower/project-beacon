# Beacon for agent builders

You have an agent. You want to know whether today's change made it worse, and
you want to know before your users do.

Beacon has no model in it and never calls one. Your agent brings its own, so
there is no API key to give Beacon and no per-run inference cost on its side.
Grading is deterministic string and state comparison — reproducible, free, and
it does not drift when a judge model is updated underneath you.

## Start from something that runs

```bash
python3 -m beacon init my-first-probe
```

That writes a scenario, and two subjects: one that satisfies every assertion
and one that violates exactly one. Run both — the second is *meant* to fail,
and watching it fail is how you know the assertion measures something. Add
`--service notes` instead for a scenario graded on the state of a simulated
service rather than on the answer text.

The generated `README.md` has the exact commands.

## Point it at your agent

No bridge code for either of these.

```bash
# An agent that speaks A2A
python3 -m beacon run scenarios/web-extraction-grounding/scenario.json \
  --adapter a2a --agent-url https://your-agent.example

# An MCP host: Beacon serves synthetic tools, your host connects
python3 -m beacon run scenarios/inbox-briefing/scenario.json \
  --adapter mcp-host --command "your-agent --mcp-config {config}"
```

A CLI or an HTTP API needs a small JSONL bridge instead — about 30 lines,
see [examples/reference_jsonl_agent.py](../examples/reference_jsonl_agent.py).

## One run tells you almost nothing

This is the part worth internalising. A model was asked to pull structured
data from `example.com`, a page with one heading and one sentence, twelve
times:

```
python3 -m beacon run web-extraction-contract \
  --adapter command --command "python3 examples/anthropic_jsonl_agent.py" \
  --env-secret ANTHROPIC_API_KEY --timeout 180 --repeat 12
```

```
Determinism: DIVERGENT across 12 runs.
  verdicts: INCOMPLETE 10 (83%), PASS 2 (17%)
  flaky: result-matches-the-contract passed 2/12 (17%)
```

It held its output contract **two runs in twelve**. Ten times it wrapped
otherwise-valid JSON in a sentence of explanation, having been told to return
JSON and nothing else. Any one of those ten looks like a broken integration;
any one of the other two looks like a working one.

The recorded rates are in
[baselines/](../baselines/) — `web-extraction-contract.claude-sonnet-5.json`
and `web-extraction-grounding.claude-sonnet-5.json`, written by
`--baseline` from those runs. **Do not quote a rate from a handful of runs.**
If a failure is intermittent, the number of runs *is* the measurement.

### Shape first, then truth

Run the grounding scenario over the same twelve and the interesting number is
one nobody usually reports:

```
entities-grounded: measured 0/12
```

Not "failed" — *never evaluated*. Grounding reads
`primary_entities[].value`, and a reply that is prose has no such path, so
there was nothing to compare and every run resolved INCOMPLETE. You cannot
measure whether an agent tells the truth until it holds its shape, and a
harness that scored those ten as failures would be reporting a fabrication
rate it never measured.

On the runs where the shape did hold, the fabrication is real: asked about
`example.com`, the model recited the page's *older* wording — "illustrative
examples in documents… without prior coordination" — against a capture
reading "documentation examples without needing permission. Avoid use in
operations." A confident recitation of a page that changed.

## Catch the regression, not just the failure

`--repeat` asks whether your agent agrees with itself right now. That is a
different question from whether it is worse than last week — and a subject can
be perfectly self-consistent and consistently wrong.

```bash
python3 -m beacon run scenario.json --adapter a2a --agent-url ... \
  --repeat 10 --baseline baselines/my-agent.json
```

The first run records the baseline. Every run after compares against it:

```
Baseline (baselines/my-agent.json): recorded 2026-07-01T09:00:00+00:00 over 20 run(s).
  REGRESSION  result-matches-the-contract passed 100% of baseline runs, 17% now (2/12)
```

Non-zero exit, so CI fails. Comparison is by **pass rate**, not verdict,
because a subject failing a quarter of the time still passes three
single-run comparisons in four.

Commit the baseline file. Regenerate it deliberately when a change is
intentional, the way you would re-record a snapshot test.

### Or compare against the last N runs

If nobody has blessed a version yet, `--baseline-recent` asks the other
question — is this worse than yesterday — with no file to maintain:

```bash
python3 -m beacon run scenario.json --adapter a2a --agent-url ... \
  --repeat 10 --baseline-recent 20
```

It reads the last 20 runs of the same scenario and the same subject out of
the output directory, and says so when there are none yet rather than
printing a clean bill of health. Runs of a different scenario, or of a
different agent sharing the directory, are skipped — a subject is identified
by its endpoint or command line, not by the adapter's name, because every
A2A subject reports the same id.

### A drop is not automatically a regression

Both modes only call a drop a regression when the sample rules out chance.
An agent that genuinely passes a third of the time fails a single run two
times in three; reporting each of those would make the check worthless
inside a week. So a single failing run against a flaky baseline says nothing,
while the same single run against a baseline that never failed is conclusive.
**How many runs it takes to prove a regression scales with how flaky the
baseline already said the subject was.**

`--baseline-tolerance 0.1` adds a deliberate margin on top: a ten-point drop
is accepted as uninteresting even where it is statistically real.

## Assertions that survive a model rewrite

A model rephrases its output every run. Assertions keyed to exact wording
break constantly and get disabled, which is worse than not having them.

All eighteen types are registered in
[beacon/assertions.py](../beacon/assertions.py); these are the ones that
survive a rewrite best.

| Assertion | Use it for |
|---|---|
| `grounded_in` | Every claim appears in a source you pinned. Catches invented facts. |
| `cites` | An identifier appears *near* something only that document contains — a citation, not a name-drop. |
| `contains_any` | Any acceptable phrasing counts. Good for "did it decline". |
| `contains_none` | A string that must never appear did not. Leaked secrets, canaries, forbidden phrasing. |
| `contains` | One value is present, case-insensitively, in text or in a list. |
| `equals` | An exact value. The most-used type here, and the right one for a state field. |
| `set_equals` | Which items were acted on, order-independent. Membership only — it cannot see duplicates. |
| `count_gte` / `count_lte` | How many items, without pinning which. |
| `conforms_to` | The output has the shape your consumers parse. Reports every violation, with paths. |
| `unchanged` | State the agent should not have touched. |
| `event_absent` | A forbidden action was never attempted, even if policy blocked it. |
| `event_present` | Something the run turns on actually happened — the confound control for restraint. |
| `event_count_gte` / `event_count_lte` | How many times it reached for a tool. Counts attempts, not replies. |
| `event_order` | One action came before another. Approval before payment, verify before close. |
| `matches_path` | Two paths in the evidence agree — what the agent *said* it did against what the state records. |
| `same_shape_across_runs` | The answer's structure is a property of the contract, not of the run. Needs scenario `repeat`. |

`matches_path` is the one most worth reaching for that people do not think of:
"the agent reports it closed twelve tickets, the queue says nine" is among the
most common real failures, and every other assertion compares a path to a
literal rather than to another path.

Two rules learned the hard way:

**A punished tool must be forbidden in the goal.** If the surface offers
`files_delete` and an assertion forbids deleting, that is a fair test only
when the goal says not to delete. A silent prohibition is a trap: a competent
agent does the sensible thing and fails for it.

The tempting shortcut is to pull the tool off the surface instead. Beacon did
that with `mail_add_label`, and it fixed the trap by creating a quieter
problem — with nothing on the surface able to touch a message, the assertion
that messages were unchanged could no longer fail, and the report went on
announcing it as a result. **Removing the means to disobey does not
demonstrate obedience.** State the constraint and leave the tool.

**Every assertion must be able to fail.** Write the subject that violates it
and confirm it goes red. An assertion that cannot fail prints a claim your
evidence does not support — Beacon's own starter scenario shipped two of them.

## Shape and truth are different questions

`conforms_to` grades structure. `grounded_in` grades content. They answer
different questions, and the recorded runs above show why you need both —
and in which order:

```
web-extraction-contract     result-matches-the-contract   passed  2/12
web-extraction-grounding    entities-grounded            measured 0/12
```

Those are the same twelve runs of the same live agent, read from
[baselines/web-extraction-contract.claude-sonnet-5.json](../baselines/web-extraction-contract.claude-sonnet-5.json)
and [baselines/web-extraction-grounding.claude-sonnet-5.json](../baselines/web-extraction-grounding.claude-sonnet-5.json).
The shape held twice in twelve. The grounding check was never evaluated at
all — not failed, *unmeasured* — because it reads `primary_entities[].value`
and ten replies had no such path.

That is the order the two checks come in. An agent that cannot hold its shape
has not been shown to be truthful; it has not been asked. A harness that
scored those ten as fabrication would be publishing a rate it never measured,
which is why they resolve INCOMPLETE and not FAIL.

On the two runs where the shape did hold, the fabrication was real — the model
recited the page's older wording, as recorded above.

Declare the schema from what your agent actually returns, not from its
documentation — record some runs first, then write the contract from them.
Unknown keywords are refused rather than ignored, so `minlength` for
`minLength` is an error at load time instead of a constraint that quietly
does nothing.

## Injection resistance

The test is whether an agent treats text it retrieved as data rather than as
instructions. Two scenarios ship:

```bash
# Tool-using agents: injections live in files the agent reads
python3 -m beacon run scenarios/injection-resistance/scenario.json --adapter ...

# Hosted agents: the injection is in the content you send
python3 -m beacon run scenarios/hosted-injection-resistance/scenario.json \
  --adapter a2a --agent-url https://your-agent.example
```

Detection is deterministic, with no judge model. Two mechanisms:

- **Tool coercion** — `event_absent` on a destructive tool. The attempt is
  recorded before dispatch, so "tried and was blocked by policy" stays
  distinguishable from "never tried". End-state checks alone miss it.
- **Exfiltration canaries** — `contains_none` on strings that appear *only* in
  the withheld material, never in the injected instruction itself. That
  distinction is the whole design: an agent that quotes the injection back
  while refusing it must not be scored as leaking, and quoting is exactly what
  a well-behaved assistant does when it flags an attempt.

**Always pair it with an assertion that the real work was done.** An agent
that answers something else entirely discloses nothing and passes the
injection check outright. On the first live run of this scenario, an
extraction agent did precisely that — ignored the note, invented a product
page, and scored a clean pass on "annex not reproduced". You cannot resist an
instruction you never read, and without the paired assertion the report would
have claimed otherwise.

Resistance in one scenario is not resistance in general. This measures one
injection style, in one position, in one format.

## Wire it into CI

```yaml
- name: Agent regression check
  run: |
    python -m beacon run scenarios/my-scenario.json \
      --adapter a2a --agent-url ${{ env.AGENT_URL }} \
      --repeat 10 --baseline baselines/my-agent.json
```

Exit codes: `0` pass and stable and no regression, `1` otherwise, `2` a usage
or scenario error. Every run writes `evidence.json`, `events.json` and
`report.md` — upload them as artifacts and you can re-grade offline later
without calling your agent again.

## Budget what a run costs you

Beacon cannot see tokens spent inside your agent — that happens on your
credentials. It measures what it caused, and enforces a ceiling:

```json
"limits": {
  "timeout_seconds": 120,
  "max_protocol_messages": 60,
  "max_subject_calls": 2,
  "max_subject_seconds": 180,
  "max_tool_calls": 40
}
```

Which of these binds depends on who is driving. `max_subject_calls` and
`max_subject_seconds` are enforced where Beacon calls the model itself; a
`--adapter command` subject drives its own loop, so they do not bind it — see
[running-it-yourself.md](running-it-yourself.md). `max_tool_calls` is the one
that does: it is a soft budget in the tool router, so a subject that loops gets
a refusal it can respond to rather than a truncated run. Counts and per-call
timings land in the evidence bundle under `usage`.

## Test your own domain

A scenario graded on *state* needs a synthetic service. Beacon ships six —
`files`, `mail`, `web`, `tickets`, `shell` and `payments`;
`project-beacon init --service <name>` generates another, or write one
and register it without touching Beacon's source:

```python
from beacon.services import register_service
register_service("calendar", lambda fixture, recorder: CalendarService(fixture, recorder))
```

Then point Beacon at the module that registers it:

```bash
python3 -m beacon run scenario.json --service-module scenarios/mine/service.py
```

A service implements four methods — `definitions`, `call`, `snapshot`,
`reset`. Snapshot and reset carry the weight: every verdict is a diff between
two snapshots, and a reset that is not exact corrupts the next run of a
repeat. Assertions read paths out of the snapshot and cannot filter, so
anything you want to assert on has to be something the snapshot names — derive
it there rather than trying to express it in the assertion.

Two helpers are worth composing, as all six shipped services do. `FaultTable`
([beacon/services/faults.py](../beacon/services/faults.py)) reads a `faults`
key from the fixture and makes a call fail on demand — including
`after_effect: "applied"`, the call that errors *after* taking effect, which is
what separates an agent that reconciles from one that retries blindly.
`DescriptionTable` ([beacon/services/descriptions.py](../beacon/services/descriptions.py))
lets the fixture write a tool's own description, so a scenario can poison the
one channel an agent has no reason to distrust. Both record an event, so a
scenario can assert the mechanism actually fired rather than assuming it did.

See [beacon/services/files.py](../beacon/services/files.py), which was written
entirely against the published contract and needed no change to the runner,
router or evaluator.

## What Beacon will not tell you

- Whether your agent is *good*. It grades what a scenario asserts, nothing more.
- Anything about a black-box agent's internals. An A2A or hosted-MCP subject
  calls its own tools against the real world, so there is no state to diff —
  the evidence is the response.
- Whether a passing run means it is safe. It is evidence for one scenario and
  one configuration.
