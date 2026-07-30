# Contributing to Project Beacon

Beacon produces evidence about how agents behave. The value of that evidence
depends entirely on it being trustworthy, so most of the rules below are about
not overstating what a run proves.

## Development setup

Beacon targets Python 3.11+ and has **no runtime dependencies**. There is
nothing to install:

```bash
git clone <your-fork>
cd project-beacon
python3 -m beacon validate scenarios/inbox-briefing/scenario.json
python3 -W error::ResourceWarning -m unittest discover -s tests -v
```

If a change requires a third-party package at runtime, it belongs behind an
optional extra with a working stdlib fallback — not in the core. `python -c
"import beacon"` must keep working in an empty environment, and CI asserts it.

## The rules that matter

**Never let "not run" become a pass.** A subject that errored, timed out, was
terminated, or failed to produce the evidence an assertion needs resolves to
`INCOMPLETE` — even if the observable assertions happened to pass. This is the
project's central invariant. See `docs/architecture.md`.

**Every run must produce an evidence bundle.** Whatever the verdict, a run that
ends without writing `evidence.json` is a bug in Beacon, not a result. Errors
inside Beacon's own evaluator are `INCOMPLETE` outcomes to be recorded, not
exceptions to be raised.

**An assertion must be able to fail.** Before adding one, write a subject that
violates it and confirm it goes red. An assertion that passes unconditionally
is worse than no assertion, because it prints a claim the evidence does not
support.

**Don't ship a tool the scenario punishes silently.** If a scenario's tool
surface advertises an action, using that action must not cause a failure
unless the goal text forbids it.

Prefer stating the prohibition in the goal over scoping the tool away. Both
fix the trap; only the first leaves the assertion able to fail. Beacon scoped
`mail_add_label` off the surface once, and the assertion that messages were
unchanged quietly became unfalsifiable — the report kept announcing it while
no tool on offer could have broken it. Removing the means to disobey does not
demonstrate obedience. `tests/test_falsifiability.py` now catches this.

**Say what a run does not prove.** Anything added to a report or the README
must be accurate about its own limits. A passing report is evidence for one
synthetic scenario and one configuration. It is not a safety certification, and
no wording should imply otherwise.

## Continuous integration is manual

Every workflow in `.github/workflows/` triggers on `workflow_dispatch` only.
Nothing runs on a push, a pull request, or a schedule, so this repository
spends no Actions minutes unless somebody deliberately starts a run.

That is a cost decision, not a quality one. Actions minutes are billed on
private repositories and the runner multipliers are uneven — Linux 1x,
Windows 2x, macOS 10x — and the CI matrix measured at roughly 104 billed
minutes per push, three quarters of it macOS. Free on a public repository;
expensive on this one.

Run the checks locally instead. They need no dependencies and take about a
minute:

```bash
python3 -W error::ResourceWarning -m unittest discover -s tests
python3 examples/subjects/run_suite.py
```

Between them that is everything CI would have run, minus the operating-system
matrix. Two Windows-specific defects have been found so far, and both are now
reproduced on every platform — see `GeneratedSourceCompilesTests` — because a
platform bug that only one runner can catch is a bug nobody catches once the
runner is switched off.

When the repository becomes public, uncomment the trigger block at the top of
each workflow. Actions is free on public repositories and the full matrix
costs nothing.

## Code conventions

- Match the surrounding style: `from __future__ import annotations`, frozen
  dataclasses for contracts, explicit exception types, no bare `except`.
- Keep the core free of runtime-specific and model-provider-specific knowledge.
  Provider bridges belong in `examples/`, per `docs/architecture.md`.
- Changes to `schemas/`, `beacon/models.py`, or `beacon/evaluation.py` change a
  published contract. Bump the relevant `schema_version` / `evidence_version`
  and say so in the pull request.

## Tests

Every behavioral change needs a test, and failure paths need them most — that
is what the project is for. New adapter or evaluator work should cover the
subject misbehaving: timing out, crashing, exiting non-zero, emitting malformed
protocol messages, or never completing.

Tests must be hermetic: no network, no reliance on the developer's environment,
temporary directories only.

## Scenarios and fixtures

All fixture data must be fully synthetic. Do not contribute real messages,
names, addresses, documents, or anything copied from a real account or product,
even redacted. Declare provenance in the scenario's `metadata`.

## Pull requests

Sign off your commits (`git commit -s`) to certify the
[Developer Certificate of Origin](https://developercertificate.org/). Describe
what you changed, how you verified it, and what the change does *not* cover.
CI must be green on all supported Python versions.

## Security

Do not open a public issue for a vulnerability. See [SECURITY.md](SECURITY.md).
