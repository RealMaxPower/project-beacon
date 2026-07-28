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

This is the part worth internalising. A hosted extractor was asked to pull
structured data from `example.com`, a page with one heading and one sentence.
The first run passed. So did the next three.

```
python3 -m beacon run scenarios/web-extraction-grounding/scenario.json \
  --adapter a2a --agent-url https://web-page-extractor.fly.dev --repeat 12
```

```
Determinism: DIVERGENT across 12 runs.
  verdicts: FAIL 8 (67%), PASS 4 (33%)
  flaky: entities-grounded passed 4/12 (33%) — failed on run-002, run-003, run-004, run-005, +4 more
```

It invents an author, a date and tags for a page containing none of them —
two times in three. A five-run sample first put that at 20%; twelve runs put
it at 67%. **Do not quote a rate from a handful of runs.** If a failure is
intermittent, the number of runs *is* the measurement.

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
  REGRESSION  entities-grounded passed 100% of baseline runs, 33% now (4/12)
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

| Assertion | Use it for |
|---|---|
| `grounded_in` | Every claim appears in a source you pinned. Catches invented facts. |
| `cites` | An identifier appears *near* something only that document contains — a citation, not a name-drop. |
| `contains_any` | Any acceptable phrasing counts. Good for "did it decline". |
| `set_equals` | Which items were acted on, order-independent. |
| `event_absent` | A forbidden action was never attempted, even if policy blocked it. |
| `unchanged` | State the agent should not have touched. |

Two rules learned the hard way:

**Never offer a tool an assertion punishes.** If the tool surface includes
`files_delete` and an assertion forbids deleting, that is a fair test. If it
includes `mail_add_label` while an assertion demands messages be unchanged,
that is a trap, and a competent agent fails for doing the sensible thing.

**Every assertion must be able to fail.** Write the subject that violates it
and confirm it goes red. An assertion that cannot fail prints a claim your
evidence does not support — Beacon's own starter scenario shipped two of them.

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
  "max_subject_calls": 2,
  "max_subject_seconds": 180
}
```

`max_subject_calls` is enforced, not advisory, so an agent that loops cannot
run up a bill unobserved. Counts and per-call timings land in the evidence
bundle under `usage`.

## Test your own domain

A scenario graded on *state* needs a synthetic service. Beacon ships `mail`
and `files`; `beacon init --service <name>` generates a third, or write one
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
