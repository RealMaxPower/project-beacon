# Contributing to Project Beacon

Beacon produces evidence about how agents behave. The value of that evidence
depends entirely on it being trustworthy, so most of the rules below are about
not overstating what a run proves.

## Conduct

[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) applies to every space this project
occupies. Reports go to conduct@beaconlab.dev, and to one person, who is also
the only maintainer — the code of conduct says so plainly and names the
escalation for a report about that person.

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

## Continuous integration

Every push to `main` and every pull request runs the full matrix — three
operating systems by three Python versions — plus the schema-conformance job,
the CLI vertical slice, the coverage floor, and the site.

The site job is the newest and exists for one reason. `vercel.json` carries a
Content-Security-Policy that the licensing and privacy page names directive by
directive, so relaxing the policy makes a published page untrue. Deployment is
automatic on merge, `vercel.json` is a file a pull request can edit, and until
that job existed the only thing checking it was `npm run headers` on one
laptop.

It did not, for the first months of this project. Actions minutes are billed on
private repositories and the runner multipliers are uneven — Linux 1x, Windows
2x, macOS 10x — and the matrix measured at roughly 104 billed minutes per push,
three quarters of it macOS. Free on a public repository; expensive on a private
one. The matrix was kept through that period rather than trimmed, so restoring
it was a one-line change.

`conformance.yml` is still manual, and permanently. It calls third-party MCP
servers and hosted agents. Free minutes changed what a weekly cron costs us and
nothing about what it costs them.

Run the checks locally first anyway. They need no dependencies and take about a
minute, which is less than waiting for a runner:

```bash
python3 -W error::ResourceWarning -m unittest discover -s tests
python3 examples/subjects/run_suite.py
```

Between them that is everything CI runs, minus the operating-system matrix.
Two Windows-specific defects have been found so far, and both are now
reproduced on every platform — see `GeneratedSourceCompilesTests` — because a
platform bug that only one runner can catch is a bug nobody catches when that
runner is the one not running.

`tests/test_workflow_triggers.py` is default-deny on workflow files: a new one
fails the suite until someone writes down what may start it.

## Code conventions

- Match the surrounding style: `from __future__ import annotations`, frozen
  dataclasses for contracts, explicit exception types, no bare `except`.
- Keep the core free of runtime-specific and model-provider-specific knowledge.
  Provider bridges belong in `examples/`, per `docs/architecture.md`.
- Changes to `schemas/`, `beacon/models.py`, `beacon/assertions.py` or
  `beacon/evaluation.py` change a published contract. Bump the relevant
  `schema_version` / `evidence_version` and say so in the pull request.
- A new assertion type is one entry in `REGISTRY` in `beacon/assertions.py`,
  one row in `CASES` in `tests/test_assertion_registry.py`, and one addition to
  the `type` enum in `schemas/scenario.schema.json`. The loader's table is a
  view over the registry, so there is no fourth place to forget. **Handlers
  return `(passed, actual, expected, message)` and raise `EvaluationError` for
  anything they cannot read** — never build an `AssertionResult` and never set
  `measured`, which is decided in one place so "we could not tell" cannot
  quietly become "the subject did the wrong thing".

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

Turn on the hook that adds the trailer for you, once per clone:

```bash
git config core.hooksPath .githooks
```

It is opt-in because git will not run a repository's files as hooks without
being told to, which is the right default and not one to work around. Without
it the rule is enforced only by a test that runs afterwards, and the gap
between the two is where every missing sign-off in this project's history came
from — including three that arrived *after* the test existed and were repaired
by rewriting history, which is a worse outcome than the flag it replaced.

The policy applies from the commit that added this sentence onward. Any commit
before it is unsigned — the requirement was written and then not followed, by
the only person contributing, until this. Those are recorded rather than fixed
by rewriting them, because a sign-off retroactively added by someone else
certifies nothing.

`tests/test_contributing_policy.py` walks the log and fails on any commit in
scope without the trailer. A history that does not contain that boundary commit
began after the policy, so the walk covers all of it — this repository's
published history is a single squashed commit, and the check used to skip
outright there, which left the rule enforced nowhere anybody could clone. The
same test keeps this paragraph and the requirement above together, so the rule
cannot go back to being stated without being kept.

**CI runs on your pull request** — see above. Say what you ran locally anyway,
and what you could not: a green check covers the matrix, not the judgement
about whether the assertion you added is one that can actually fail.

## Security

Do not open a public issue for a vulnerability. See [SECURITY.md](SECURITY.md).
