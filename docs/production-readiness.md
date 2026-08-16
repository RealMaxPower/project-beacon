# Production readiness

What Beacon is ready to be trusted with, what it is not, and what would change
each answer.

The README says what the project does. This is the ledger behind it: the
limitations in detail, the operational state of this repository, and the
specific evidence for each claim. It exists because a limitation compressed to
half a bullet stops being checkable — and a reader who finds one claim wrong
stops believing the rest of the page.

**Status: v0.1, alpha.** Nothing has been released. The version is duplicated in
`pyproject.toml` and `beacon/__init__.py`, and the release workflow asserts a
tag matches the first.

## Verdict by use case

| Use it for | Ready | Why |
|---|---|---|
| Grading your own agent against a scenario you wrote | **Yes** | The CLI, the adapters, the assertion engine and the evidence bundle are the parts that are exercised hardest |
| Grading against the scenarios that ship | **Yes** | Eighty-three of them across six synthetic services — mail, documents, a simulated web, a support queue, a shell that runs nothing, and a ledger — with declarative fault injection and a published taxonomy saying what they do and do not cover |
| Regression-gating an agent in your own CI | **Yes** | Baselines, flakiness rates and a significance test all work; `docs/agent-builders.md` is the path |
| Probing an agent that might be actively hostile | **Not yet** | The process runner is not a sandbox. A container runner is planned — see *Isolation* |
| Publishing evidence a third party must trust | **Not yet** | The digest is unsigned and no command verifies one. Both are planned — see *Evidence integrity* |
| Installing it as a dependency | **Not yet** | Nothing is on PyPI. The release pipeline is built and tested — see *Distribution* |
| Driving a run from a browser | **No, by decision** | The CLI is the interface. See *Decided against* |
| Approving an agent's actions as it works | **No, by decision** | Scenario policy is the mechanism, and unlike a human it is deterministic. See *Decided against* |
| Deciding whether an agent is safe to deploy | **No** | A passing report is evidence for one synthetic scenario and one configuration. It is not a safety certification, and never will be |

## What is not ready, in detail

### Isolation

The subject runs as a child process with the environment Beacon hands it. There
is no container, no VM, no seccomp profile, and no egress firewall. A subject
that wants to read the filesystem outside the run directory, open a socket, or
spend the caller's credentials on something unrelated can do so.

This is the single largest gap, and it bounds everything else: the synthetic
services are a *fixture*, not a *containment boundary*. They exist so a run is
repeatable and resettable, not so a hostile subject is confined. `SECURITY.md`
states the same thing and is the authority.

**What would change it:** a container runner with a declared egress policy. This
is planned.

### Cost accounting, and the line between measured and claimed

`beacon/usage.py` records what Beacon *caused*: how many requests were made,
how long each took, and how many failed. A scenario's declared
`max_subject_calls` is enforced as a real ceiling rather than reported after
the fact — but only where Beacon drives the model itself. A `--adapter command`
subject runs its own loop, so the ceiling that binds it is `max_tool_calls`, a
soft budget in the tool router: the subject gets a refusal it can respond to
and can still finish, rather than being cut off mid-run.

Naming the wrong key here would be the failure this page is about. It said
`max_calls` for a while, which is the `UsageRecorder` constructor parameter and
not a scenario key at all — a scenario declaring it would have been silently
ignored, exactly the way a misspelled limit takes the default.

Beacon still cannot *observe* tokens or money. That spend happens inside
someone else's infrastructure on their model credentials, and no amount of
harness work gives Beacon a view of it.

What a subject can do is say what it spent, and that is now collected:
`usage.reported` in the bundle, carrying totals and one entry per source. Three
routes feed it — a JSONL subject's `complete.metadata.usage`, an A2A task or
message's `metadata.usage`, and an MCP result's `_meta.usage`. The bundled
`examples/anthropic_jsonl_agent.py` reports its own, summed across turns rather
than read off the last response, because a tool-using run is several billed
requests.

**The separation is the design, not an implementation detail.** Everything else
under `usage` is something Beacon watched happen. A reported token count is a
claim by the party under evaluation — the same kind of evidence as the answer
being graded — so it sits under its own key, carries a note saying where it came
from, and adds a line to the run's `limitations`. A bundle that mixed the two
would present an unverifiable figure with the authority of a measurement, which
is the failure this project exists to catch, in the format hardest to notice.

Two things this deliberately does not do. It does not convert tokens to money:
that needs a price table, prices move, and a stale figure presented as cost is
worse than no figure. And it does not validate the numbers, because it cannot —
a subject that under-reports is not detectable from here.

`estimated_cost_usd` used to be declared in two scenarios and read by no code,
so it reached every bundle they produced as a dollar figure beside measured
ones. It has been removed, and `tests/test_falsifiability.py` now fails any
scenario declaring a limit nothing enforces — which also catches a misspelled
`timeout_second` silently taking the default.

**What would change the rest:** nothing generic, and that is the honest answer.
Observed cost would require the subject's provider credentials, which Beacon
should never hold.

### Evidence integrity

Every bundle carries a SHA-256 digest over its canonical form, and
`project-beacon verify <evidence.json>` recomputes it:

```console
$ project-beacon verify .beacon/runs/run-29c153bbe9f5/evidence.json
VERIFIED: .beacon/runs/run-29c153bbe9f5/evidence.json
```

It exits 1 and reports `MODIFIED` when the document no longer matches its own
digest, and distinguishes that from a bundle written by a newer Beacon — an
unknown field means this version cannot interpret the file, which is not the
same accusation as tampering.

The digest is **unsigned**, and that is the limit worth understanding. It shows
a bundle was not edited after the run. It does not show which machine produced
it, or that the run happened at all: whoever holds the file can change it and
recompute the digest to match. A digest is an integrity check between you and a
copy of your own evidence, not a claim a third party can rely on.

Verification found its first defect immediately. Every bundle published on the
site failed it, because `site/tools/build_fixtures.py` replaces the recording
machine's path with a placeholder *after* the run seals itself — so each one
shipped a digest over a document that no longer existed, beside a paragraph
promising a digest makes an edit detectable. Nothing caught it because nothing
could check a digest. Those bundles are now resealed over the published
document and say in their own `limitations` that a path was substituted;
`tests/test_verify.py` fails if a published bundle stops verifying.

**What would change the rest:** signing with a key the reader can check. The
crypto is the easy half — key distribution is the problem, and the likely
answer is keyless OIDC signing so there is no secret to leak and the identity
is the workflow rather than a file.

### Distribution

Nothing has been published to PyPI, so `pip install project-beacon` does not
work. Packaging is in better shape than that implies: the release workflow
builds an sdist and a wheel, runs `twine check --strict`, installs the wheel
into a clean virtualenv in an empty directory, exercises the CLI paths a new
user takes, then unpacks the sdist and runs the shipped test suite out of it.

That last step exists because the smoke test used to run only the subset of
commands that needed no data files, and stayed green for weeks while the sdist
shipped without `examples/`, `docs/`, `schemas/` or `tests/stubs/` — so the
suite it did ship could not run.

**What would change it:** tagging `v0.1.0`, which publishes through PyPI
trusted publishing with no long-lived token in the repository.

### Runtime adapters

There is no OpenClaw, Hermes, Codex, or other native runtime adapter. The
compatibility model's Level 4 promises runtime configuration, approvals, cost
and richer traces; the only Level 4 subject today is Beacon's own in-process
reference agent, where Beacon *is* the runtime.

That pair is easy to misread. A default run's evidence says
`Integration: in-process (level 4)` while this document says there is no native
runtime adapter. Both are true: no adapter exists for anyone *else's* runtime,
and the two rungs promising approvals and cost are promising evidence Beacon
does not yet collect from any subject.

### Service virtualization proxy

There is none. A proxy that recorded a real service and replayed it would be
useful, and the mechanism to build one already exists: `--service-module` loads
a service by path, and `examples/scenario-pack/` proves a pack can bring its own
without editing Beacon.

The constraint is that `call()` must be deterministic and `reset()` must restore
the seed exactly — verified by digest equality on every run. A live passthrough
to a real service satisfies neither and would silently set
`reset_verified: false` in every bundle, so record-and-replay against a cassette
is the only design that keeps `--repeat` and baselines meaning what they say.

**What would change it:** a scenario pack, not a change to the core.

## Decided against

These are not gaps waiting on time. They were considered and rejected, and they
are recorded here because a permanent "not yet" reads as a promise. A project
that argues claims should be checkable should not keep a list of things it has
quietly stopped intending to build.

### A web UI that runs scenarios

**The CLI is the interface.** Beacon is for people who build agents, and they
already run things from a terminal and wire them into CI. A second way to
start a run would be a second surface to keep honest, for an audience that did
not ask for it.

`site/` stays what it is, and calling it nothing would be its own inaccuracy: a
marketing site plus a playground with a full run flow — pick a scenario, pick a
subject, see the world before, watch the timeline, read the verdict, compare
twelve runs against a baseline, export the bundle. What it does not do is *run*
anything. It makes no network calls at all — its Content-Security-Policy sets
`connect-src 'none'`, deliberately — and every screen replays evidence recorded
from real runs by `site/tools/build_fixtures.py`.

The fixtures are recorded rather than hand-written for the same reason. A
plausible `evidence.json` that does not match the real one is worse than no
expert view at all, because the expert view is the one built for people who will
not trust a friendly summary.

### An approval interface

**Scenario policy is the mechanism, and it is deterministic.** A scenario
already says what is forbidden — `allow_send`, `allow_delete`, and the tool
surface itself — and a refusal is recorded as an attempt before the gate, so the
evidence shows what the subject tried whether or not it succeeded.

A human approving calls mid-run would break the property the rest of the project
rests on. `--repeat` and baseline regression detection both assume a run is
reproducible; a person deciding differently on Tuesday makes the same subject
and the same scenario produce a different verdict, and there would be no way to
tell that from a real regression. What makes a Beacon verdict worth reading is
that nobody was in the loop.

### A hosted service

Not planned, which follows from the first two. Running strangers' agents would
make the container sandbox a hard prerequisite rather than a planned
improvement, and would add accounts, abuse controls and cost controls — none of
which grade an agent any better than the CLI already does.

The site has a page about this, and it is a question rather than a promise:
"There is no hosted lab yet. This is the page where I ask whether there should
be." It carries no waitlist form, deliberately, because collecting addresses
creates an obligation with nothing behind it. That page stays. An open question
asked in public is not the same as a roadmap item, and this document should not
pretend the question has been closed when it has only been answered *for now*.

## Licensing, and the file that is deliberately absent

Project Beacon is Apache 2.0. The `LICENSE` file carries the full text, the
appendix, and a copyright line naming Marshall Cahill and Project Beacon contributors —
matching `pyproject.toml`, pinned to it by `tests/test_licensing.py` so the two
cannot drift into naming different parties.

**There is no `NOTICE` file, and that is a decision.** Apache 2.0 §4(d) obliges
a redistributor to propagate one only *if it exists*. The Python package has
`dependencies = []` and vendors nothing, so there is no third-party
attribution to carry. A `NOTICE` here would repeat what `LICENSE` already says
while creating a propagation obligation for everyone downstream — a rule with
nothing behind it, which is the shape of thing this project argues against.

Two other licences do have attachment requirements, and both are met by files
rather than by sentences:

- **The typefaces** are redistributed under the SIL Open Font Licence 1.1,
  which permits that only with the licence attached.
  `site/public/fonts/OFL.txt` carries it, with each upstream's copyright notice
  reproduced verbatim. Subsetting makes these Modified Versions, and OFL
  clause 3 forbids a Modified Version from using a Reserved Font Name — which
  is why IBM Plex could not ship and Inter took its place.
- **The bundled JavaScript** is MIT, and every visitor receives a compiled copy
  of React. The built assets carried no notice at all until
  `site/public/THIRD-PARTY-NOTICES.txt` was added — generated from the
  installed packages, and pinned by a test that reads the lockfile so a new
  runtime dependency is covered the moment it is installed. The build also
  keeps the inline `@license` blocks it used to discard.

The site's `#/legal` page links both, states the licence, and describes what
the site collects. That page is short because the answer is short: no cookies,
no analytics, no forms, and a Content-Security-Policy declaring
`connect-src 'none'`, so the page cannot transmit anything anywhere. What
remains is what any web server sees, and the page says so rather than implying
the logs do not exist.

**Not resolved:** the name. The pre-build proposal scheduled a naming and
trademark screen that never happened, and "Beacon" is a heavily used word. The
wordmark is monochrome geometry specifically so that a rename costs one string,
but the search itself is still outstanding.

## Security posture

[SECURITY.md](../SECURITY.md) is the authority and is candid about the known
limitations. The short version: no sandbox, no egress firewall, unsigned
digests, and CLI auth values visible in process arguments on a shared machine.

Credentials are passed by name, never by value — `--env-secret` takes the name
of an environment variable, Beacon reads the value from its own environment,
hands it to the subject, and redacts it from the evidence bundle wherever it
appears including common re-encodings. That is a containment measure rather
than a guarantee, and `REDACTION_NOTICE` states the limit inside every bundle
where it is in use.

The command line itself is written verbatim into `evidence.json`, so a key
typed on it would be published in the artifact you share.

## Operational state of this repository

These are facts about the repository rather than the software, and none of them
is visible from a checkout.

**Three workflows are disabled at the GitHub level.** `ci.yml`, `release.yml`
and `conformance.yml` all report `disabled_manually` from the Actions API. The
trigger blocks in the YAML are live, but the Actions-tab switch overrides them,
so a push to `main` starts nothing. Editing triggers in git does not change
this; re-enabling is an API call or a click per workflow. This is exactly the
invisible state that `tests/test_workflow_triggers.py` was written to argue
against, and it is not something that test can see.

**A fourth workflow is active and outside the gate.** GitHub generates a
Dependabot Updates workflow from `.github/dependabot.yml`. It never appears in
`.github/workflows/`, which is the only directory
`tests/test_workflow_triggers.py` reads — so the default-deny classification
that fails the suite for an unclassified workflow did not see it arrive. The
configuration itself is deliberately narrow: monthly, grouped into one pull
request per ecosystem, and no pip ecosystem at all because the package has no
runtime dependencies.

**`conformance.yml` should stay manual permanently.** Its cost reason expired
when the repository was published; its real reason did not. It calls
third-party MCP servers and hosted agents belonging to people who did not ask
to be measured.

## What this document is not

It is not a threat model, and it is not an audit. It is the maintainer's own
account of what is finished, written to be checkable: every claim above names
the file, command or API response behind it, so a reader who doubts one can go
and look rather than take it on trust.

If a claim here is wrong, that is the most valuable bug report this project can
receive — see [CONTRIBUTING.md](../CONTRIBUTING.md).
