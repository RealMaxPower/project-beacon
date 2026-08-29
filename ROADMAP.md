# Roadmap

What is committed, what is being investigated, and what has been decided
against.

This file exists because the answer was in three places and none of them was
this one: *What would change it* in
[docs/production-readiness.md](docs/production-readiness.md), *Still planned* in
[docs/architecture.md](docs/architecture.md), and a question the site asks about
a hosted lab. A reader who wanted to know where the project was going had to
assemble it from three documents written for other purposes, and could not tell
which items were commitments and which were musings.

## What this file is not

**There are no dates on it.** This is one maintainer's project, and a quarter
typed beside an item would be a claim with nothing behind it — the exact shape
of thing the README spends a page arguing against. What each entry carries
instead is **what would change its status**, which is the part a reader can
check.

**There are no counts on it either.** Every figure this project publishes is
computed by a test from the file that holds it, and a roadmap is the one
document with no such file behind it. Where a number matters below, the command
that prints it is named instead: `project-beacon scenarios`,
`project-beacon taxonomy`, `project-beacon adapters`.

## The ordering, and why

**Reach before trust.** The isolation gap and the unsigned digest are the two
things `docs/production-readiness.md` marks **Not yet**, and they are the more
interesting engineering. They are not first.

The reason is that the scenarios that ship cannot currently be run at the scale
they were written for. `run` takes one scenario; `--repeat` and `--baseline` are
per-scenario; `baselines/` holds one file per scenario and subject. An agent
builder who wants what [docs/agent-builders.md](docs/agent-builders.md) promises
— regression-gating in CI against the shipped corpus — has to write their own
loop, their own aggregation and their own exit-code policy. Everything else in
this project is finished to a standard that gap makes unreachable.

The isolation gap, by contrast, is disclosed, bounded, and correct for the use
case people actually have today: grading an agent you wrote against scenarios
you chose. It stops being acceptable when strangers' agents run here, which is a
thing nobody is asking for yet.

---

## Committed

### Suite-scale runs

**Why.** See above. It is the difference between a corpus and a demonstration.

**Shape.** A `suite` subcommand: many scenarios per invocation, one aggregate
bundle, one exit code. Selection by family and by taxonomy cell, both of which
are metadata `beacon/taxonomy.py` already parses. `--jobs` for concurrency —
each run prepares fresh services and verifies its own reset, so runs are
independent by construction and the real ceiling is the subject's rate limit,
which is the caller's to set. `beacon/baseline.py` grows a suite-level baseline
reusing the significance test that is already there, rather than a second
implementation of the same statistics.

`run_scenario` does not change. A suite is a loop and an aggregator, not a
second engine, and a run inside a suite must produce the bundle it would have
produced alone or the aggregate is describing something else.

**Done when.** `--jobs 4` and `--jobs 1` produce identical verdicts over the
same selection — the determinism property this project already asserts about
subjects, turned on the suite runner itself — and a family selection matches
exactly what `project-beacon taxonomy --json` reports for that family.

### Machine-readable CI output

**Why.** A suite result that only a human can read is not a gate.

**Shape.** JUnit XML, because every CI system already reads it, plus a GitHub
job summary and inline annotations behind a flag.

The interesting part is the mapping, not the format. `PASS`, `FAIL` and
`INCOMPLETE` are three states, and JUnit has three: passed, failure, skipped.
Most eval tooling collapses "could not tell" into "failed", which is the single
thing [docs/architecture.md](docs/architecture.md) result semantics exist to
prevent. Emitting an `INCOMPLETE` as a JUnit failure would undo that at the
export boundary, where nobody would look for it.

**Done when.** A test asserts an `INCOMPLETE` verdict is exported as skipped and
not as failure. That test is the feature; the XML is the packaging.

### A published GitHub Action

**Why.** A `uses:` block in a README is the difference between a project people
read about and one they install. A thin wrapper over the two items above.

**Done when.** The README's quickstart can show a workflow file that runs
against a fork with nothing else configured.

### Evidence signing

**Why.** *Publishing evidence a third party must trust* is **Not yet** in the
readiness ledger, and the reason is precise: the digest shows a bundle was not
edited after the run, and nothing more. Whoever holds the file can change it and
recompute the digest to match. That makes it an integrity check between you and
a copy of your own evidence — useful, and not what the word evidence implies to
a reader.

This is also the item that completes the project's own argument. A harness whose
thesis is that a claim needs a mechanism behind it currently asks to be taken at
its word about the provenance of its output.

**Shape.** Keyless OIDC signing over the canonical digest that already exists,
and `verify --signature`. The crypto is the easy half; key distribution is the
problem, and keyless is the answer that leaves no secret to leak.

**Done when.** A signed bundle verifies, a mutated one fails, and the failure is
distinguishable from "written by a newer Beacon" — a distinction `verify`
already draws and must keep drawing, because an unknown field is not the same
accusation as tampering.

### A container runner

**Why.** The readiness ledger calls isolation "the single largest gap, and it
bounds everything else". The synthetic services are a fixture, not a containment
boundary: a subject that wants to read the filesystem outside the run directory,
open a socket, or spend the caller's credentials elsewhere can do so.

**Shape.** A selectable runner for the command adapter, with a declared egress
policy. The process runner stays the default, because the zero-dependency
property is worth more than a default nobody can satisfy without a daemon
installed. Which runner ran is recorded in the bundle — it is a condition of the
run, exactly like a budget override, and a bundle that does not say which one it
used is describing an experiment it has not fully specified.

**Done when.** A subject that reads outside its run directory succeeds under the
process runner and is refused under the container runner. That pair is the
proof, and it is the falsifiability rule applied to an isolation claim: an
assertion nobody has watched fail is a claim the evidence does not support, and
that is as true of a containment boundary as of a scenario.

---

## Investigating

Not commitments. Each is a question with a criterion for answering it.

### Widening the taxonomy again

Coverage is at 100%, and the README says at length that this is the least
informative state its table can be in — that the figure is meant to fall, and
has, twice. The project's own logic therefore says the list is due to widen,
and the honest reason it has not is that nobody has done the screening.

Candidates worth screening: multi-agent handoff fidelity, refusal calibration
(the shipped corpus has one control for over-refusal and nothing measuring the
other direction), tool-schema drift mid-run, personal-data handling,
non-English and multilingual injection, and resource exhaustion.

**The criterion is the existing one.** Each has to survive
distinct/buildable/consequential/attributable, per
[docs/failure-taxonomy.md](docs/failure-taxonomy.md), or go into `out_of_scope`
naming the test it failed. A candidate is never excluded for being hard or
unbuilt, and the point of publishing the rejections is that the denominator
cannot be quietly trimmed until the numerator looks good.

### Published cross-model results

`baselines/` records one scenario against a ladder of small local models and two
against one hosted model. That is enough to support the sentences the
documentation quotes and not enough to be a result anybody would cite.

Running a real slice of the shipped corpus against several models and committing
the baselines is the artifact most likely to make this project useful to
somebody who will never run it. It is also the artifact most easily
overinterpreted, which is the reason it sits here rather than above: a
comparison table is read as a ranking whatever its caveats say, and this project
would be publishing one about other people's systems.

**Prerequisite.** Suite-scale runs. This is that feature's first real customer,
which is part of why it is first.

### Native runtime adapters

The compatibility model's Level 4 promises runtime configuration, approvals,
cost and richer traces, and the only Level 4 subject is Beacon's own in-process
reference agent — where Beacon *is* the runtime. Adapters for the runtimes
people actually build on would make that rung mean something.

Lower priority than it looks. The JSONL bridge already reaches all of them at a
lower integration level, so this buys evidence *depth*, not access. And per
[CONTRIBUTING.md](CONTRIBUTING.md) these ship as bridges under `examples/`: the
core stays ignorant of any particular runtime or model provider, which is the
property that lets it be pointed at the next one.

### A hosted lab

**Still a question, and this file does not close it.** The site has a page that
asks whether there should be one, carrying no waitlist form, deliberately,
because collecting addresses creates an obligation with nothing behind it.

It is listed here rather than under *Decided against* because the readiness
ledger is careful about the difference: the question has been answered *for now*
and not settled. What it would require is not in doubt — running strangers'
agents makes the container runner a hard prerequisite rather than a planned
improvement, and adds accounts, abuse controls and cost controls, none of which
grade an agent better than the CLI already does.

---

## Decided against

Three things were considered and rejected: a web UI that runs scenarios, an
approval interface, and a hosted service.

They are recorded in
[docs/production-readiness.md](docs/production-readiness.md#decided-against)
with the reasoning, and are deliberately not restated here — two copies of a
decision is one copy that goes stale. That section exists because a permanent
"not yet" reads as a promise, and a project arguing that claims should be
checkable should not keep a list of things it has quietly stopped intending to
build.

---

## How this file stays true

Roadmaps rot faster than any other document in a repository, and this one is
structurally hard to guard: an intention has no file behind it to compute from.

Three things limit the damage. It carries **no dates and no counts**, which are
the two things that go stale without anybody editing them. Every link in it is
checked by `tests/test_documented_claims.py`, along with every other markdown
file this repository tracks. And an item that ships must move out of *Committed*
in the same change that adds it, because the changelog entry and this file are
describing the same event — a roadmap still promising a feature that shipped
last month is the version of this document that teaches people not to read it.
