# Adversarial subject suite

Thirteen subjects that behave the way a real agent plausibly does, run against
`scenarios/inbox-briefing`. None of them import `beacon` — they speak the JSONL
bridge protocol in `docs/protocol-contracts.md`, exactly as an external agent
would.

```bash
python3 examples/subjects/run_suite.py
python3 examples/subjects/run_suite.py --keep-evidence .beacon/suite
```

## Why this exists

Until this suite, every subject Beacon had ever graded was written by Beacon,
against the assertions doing the grading. That proves the pipeline runs; it
proves nothing about whether the verdicts are right.

Six of these thirteen currently get the wrong verdict — and the failures are
not close calls. A subject that completes the task correctly and takes three
seconds to shut down is reported `INCOMPLETE` with all seven assertions
passing. A subject that labels the mail it handled, using a tool Beacon
advertised to it, is reported `FAIL`.

Running an expensive model against a harness in this state produces a result
nobody can interpret: a `FAIL` could mean the model did badly, or that it
named its output `briefing` instead of `summary`. These subjects are free,
deterministic, and isolate every one of those confounds.

## How the manifest works

`manifest.json` records two verdicts per subject:

- `should_be` — what a correct Beacon returns.
- `currently` — what Beacon returns today.

When they differ, `defect` explains why. `tests/test_adversarial_subjects.py`
asserts `currently`, so the suite stays green while defects are open and turns
red the moment one is fixed. That failure is the reminder to update the
manifest — the record cannot silently drift from reality.

`test_manifest_defects_match_the_recorded_verdicts` keeps the bookkeeping
honest in both directions: a wrong verdict must carry a defect note, and a
correct one must not.

## The one invariant that outranks the verdict

`test_every_run_produces_an_evidence_bundle` asserts that all thirteen
subjects — including the one that crashes, the one that corrupts stdout, and
the one that hangs — produce `evidence.json` and `report.md`. A run that ends
without an evidence bundle is a bug in Beacon, whatever the subject did.

## Adding one

Write the subject, run the suite to see what Beacon actually does, then add the
entry. Record what you observed in `currently`, not what you hoped for. If it
differs from `should_be`, say why in `defect`.

Per CONTRIBUTING.md: before adding an assertion, write the subject that makes
it fail. This directory is where that subject goes.
