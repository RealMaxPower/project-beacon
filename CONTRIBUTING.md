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

**Don't ship a tool the scenario punishes.** If a scenario's tool surface
advertises an action, using that action must not cause a failure unless the
goal text forbids it. Scope the tool surface instead.

**Say what a run does not prove.** Anything added to a report or the README
must be accurate about its own limits. A passing report is evidence for one
synthetic scenario and one configuration. It is not a safety certification, and
no wording should imply otherwise.

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
