# Verifying a checkout

For someone who did not write this, on their own machine, before it goes
public. It is written to be worked through top to bottom by a person or by an
agent; nothing in it needs a key, a network, or an account, except the two
sections that say so.

Every expected value below was read off a real run rather than remembered. **If
a number here disagrees with your terminal, one of the two is a bug — say which
you saw.** That is the same rule the project applies to itself, and this
document is not exempt.

---

## 0 · Before you start

Three things must not happen while this repository is private.

- **Do not `git push`.** The remote is private, and the branch is 20-odd
  commits ahead of `main`. Nothing here needs pushing.
- **Do not enable the GitHub Actions workflows.** All three are
  `disabled_manually`. Actions minutes are billed on private repositories and
  macOS bills at 10×; the matrix measures around 104 billed minutes per push.
  Everything CI runs is in §2 and §3 below, which is the point of them.
- **Do not `vercel deploy --prod`.** A preview is fine and costs nothing.

If you break something while working through §5, `git checkout -- .` puts it
back. Nothing in this plan asks you to keep an edit.

### What you need

Python 3.11 or newer, and nothing else for §1–§4. Node 20+ for §6. That is not
a simplification — the core has no runtime dependencies and the suite runs in
an empty environment, which §3 asks you to prove rather than believe.

```bash
git clone <this repository>
cd project-beacon
python3 --version        # 3.11, 3.12 or 3.13
```

---

## 1 · The two commands that gate a change

```bash
python3 -W error::ResourceWarning -m unittest discover -s tests
python3 examples/subjects/run_suite.py
```

Expect:

```
Ran 868 tests in ~115s
OK
```

```
415/415 verdicts correct.
```

Together they take about four minutes. The second one prints a line per
subject; the last line is the one that matters.

**It is a bug if** the first command reports a `ResourceWarning`. It is run
with `-W error::ResourceWarning` on purpose — a leaked subprocess or file
handle fails the suite rather than printing a warning nobody reads.

**It is a bug if** `run_suite.py` prints anything under "Open defects" or
"Manifest drift". Both mean the recorded expectation and the observed verdict
have parted company, which is the one thing that suite exists to catch.

---

## 2 · What CI would have caught

CI runs these across three operating systems and three Python versions. You are
one machine, so you are covering roughly a ninth of it — worth knowing, not
worth apologising for.

```bash
# The core imports with nothing installed
python3 -c "import beacon; print(beacon.__version__)"        # 0.1.0

# The CLI vertical slice
python3 -m beacon validate scenarios/inbox-briefing/scenario.json
python3 -m beacon run scenarios/inbox-briefing/scenario.json
python3 -m beacon run scenarios/inbox-briefing/scenario.json \
  --adapter command --command "python3 examples/reference_jsonl_agent.py"
python3 -m beacon run scenarios/inbox-briefing/scenario.json \
  --adapter mcp-host --command "python3 examples/mcp_host_agent.py"

# Cross-run determinism
python3 -m beacon run scenarios/inbox-briefing/scenario.json --repeat 5

# The coverage floor
python3 -m pip install coverage
python3 -m coverage run --source=beacon --branch -m unittest discover -s tests
python3 -m coverage report --fail-under=80
```

Expect `PASS` from each run, `Determinism: STABLE across 5 runs`, and a
coverage total of **88%** against a floor of 80.

**It is a bug if** `--repeat 5` reports `DIVERGENT`. Every subject in this
repository is deterministic; divergence means state leaked between runs, which
would put every verdict in the project in doubt.

**It is a bug if** the MCP host slice hangs. It starts a local HTTP façade with
a per-run bearer token and should finish in a second or two.

### Optional: the schema extra

```bash
python3 -m pip install ".[validate]"
python3 -m unittest tests.test_schema_conformance -v
```

The loader enforces the scenario contract in code whether or not `jsonschema`
is installed. This checks the published JSON Schemas agree with it.

---

## 3 · The zero-dependency claim, tested rather than believed

```bash
python3 -m pip install build twine
python3 -m build
python3 -m twine check --strict dist/*

python3 -m venv /tmp/fresh
/tmp/fresh/bin/pip install dist/*.whl
mkdir -p /tmp/elsewhere && cd /tmp/elsewhere

/tmp/fresh/bin/project-beacon --version      # 0.1.0
/tmp/fresh/bin/project-beacon scenarios      # 83 of them
/tmp/fresh/bin/project-beacon taxonomy       # 131 of 131
/tmp/fresh/bin/project-beacon run inbox-briefing
cd -
```

`/tmp/elsewhere` matters: it proves the package carries its own scenarios and
taxonomy rather than finding them by being run inside the checkout.

**It is a bug if** `scenarios` or `taxonomy` comes back empty from outside the
repository. That is the failure mode a wheel has and a checkout hides.

**It is a bug if** anything in the venv besides `project-beacon` is installed.
`pip list` should show pip, setuptools and nothing else.

---

## 4 · The published figures

```bash
python3 -m beacon taxonomy
```

```
Failure taxonomy 1.2.0
  131 of 131 cells this build can grade (100%)
  131 of 131 cells overall (100%)
  24 candidates considered and rejected
```

Read 100% as **"this list is exhausted"**, never as "agent failure is". The
denominator is a list this project chose, and the README says so.

Then check the number is computed rather than typed:

```bash
# Break the README's coverage sentence and watch a test fail
sed -i.bak 's/cover 131 of the 131/cover 130 of the 131/' README.md
python3 -m unittest discover -s tests -p "test_taxonomy_coverage.py"   # must FAIL
mv README.md.bak README.md
```

**It is a bug if** that passes. The figure in the README is pinned to the one
`beacon taxonomy` computes; if prose and code can disagree silently, the number
means nothing.

---

## 5 · Try to falsify the claims

This is the part worth your attention. §1–§4 run the project's own checks,
which is what the author already did. These four ask whether the properties the
project advertises are real.

### 5.1 "Assertions have to be falsifiable"

```bash
python3 -m unittest discover -s tests -p "test_falsifiability.py"
```

Now add an assertion nobody can fail. Open any scenario in `scenarios/` and
append this to its `assertions` array:

```json
{"id": "cannot-fail", "type": "contains_none", "path": "artifacts",
 "expected": ["zzqx-a-string-no-fixture-contains"],
 "description": "An assertion no subject can break"}
```

Re-run the same test. **It must fail**, naming `cannot-fail` as unproven.
`git checkout -- scenarios/` to undo.

The string matters. A first draft of this section used `equals` on
`subject.status` — and the guard passed, correctly: every scenario ships a
subject that escalates, which fails that predicate, so the assertion was
falsifiable after all. An assertion is unfalsifiable only when *no* subject in
the manifest can make it fail, which is why the example above searches for a
string no fixture contains.

**It is a bug if** it passes. An assertion nobody has watched fail is a claim
printed in `report.md` that the evidence does not support, and this guard is
the reason the project can say otherwise.

### 5.2 "Not run never becomes a pass"

```bash
python3 -m beacon run inbox-briefing \
  --adapter command --command "python3 -c 'import sys; sys.exit(1)'"
```

Expect **INCOMPLETE**, not FAIL and never PASS. A subject that never ran has
told you nothing, and a harness that scored silence as success would be worse
than no harness.

### 5.3 The graded agent is not handed the answer key

```bash
python3 -c "
from beacon.models import Scenario
s = Scenario.load('scenarios/injection-resistance/scenario.json')
print('sent to the subject:', sorted(s.public_dict()))
print('metadata sent?     ', 'metadata' in s.public_dict())
print('kept in evidence?  ', 'metadata' in s.recorded_dict())"
```

Expect `metadata sent? False` and `kept in evidence? True`. Scenario metadata
is where authors leave notes for each other, and it once told the agent under
test where the exfiltration canary lived. It is withheld from the subject and
kept in the bundle, because a reader of `report.md` is not the thing being
measured.

**It is a bug if** any string a `contains_none` assertion searches for appears
in what the subject is told. `tests/test_scenario_contract.py` checks the
general property; this is the one-line version.

### 5.4 A bundle that changed after the run says so

```bash
python3 -m beacon run inbox-briefing --output /tmp/vfy
B=$(ls -d /tmp/vfy/*/)evidence.json
python3 -m beacon verify "$B"; echo "exit $?"        # exit 0

python3 -c "
import json; p='$B'; d=json.load(open(p))
d['assertions'][0]['passed'] = False
json.dump(d, open(p,'w'))"

python3 -m beacon verify "$B"; echo "exit $?"        # exit 1
```

The second run must report that the bundle does not match its own digest, and
exit non-zero. Note the honest limit, which `verify` prints itself: the digest
shows a bundle changed after the run. It does **not** show which machine
produced it, or that the run happened at all. It is not a signature.

---

## 6 · The site

```bash
cd site
npm install
npm run check
```

Expect `No rendering defects found.`, `Fixtures reproduce. 121 files checked.`
and `public/THIRD-PARTY-NOTICES.txt is current.`

Heavier, and needs browsers:

```bash
npx playwright install --with-deps chromium
npm run headers      # the CSP as served, not as written
npm run visual       # overlap, overflow, tap targets, 12 routes × 5 widths
node tools/flow.mjs  # the playground actually reaches a verdict
```

**It is a bug if** `npm run headers` passes while the pass-rate bars are
invisible in `npm run dev`. The Content-Security-Policy is the one thing that
cannot be reviewed by reading it — `style-src 'self'` looks like it forbids the
inline widths and does not, because React sets them through the CSSOM.

For the manual walk of the screens, see [`site/TEST-PLAN.md`](../site/TEST-PLAN.md).
Its §1 is known stale and says so at the top; §2–§5 are current.

---

## 7 · A model as the subject

Optional, and the only part that can cost money. **The free path first:**

```bash
# With Ollama running locally — no key, no network, no spend
python3 -m beacon run inbox-briefing \
  --adapter command \
  --command "python3 examples/openai_jsonl_agent.py \
             --base-url http://localhost:11434/v1 --model qwen2.5" \
  --timeout 180
```

Any verdict is a valid result here, including INCOMPLETE — a small local model
failing to hold an output contract is a finding, not a broken harness. What you
are checking is that the wiring works end to end.

The paid path needs a key in your environment, never on the command line:

```bash
export OPENAI_API_KEY=sk-...
python3 -m beacon run inbox-briefing \
  --adapter command --command "python3 examples/openai_jsonl_agent.py --model gpt-4o" \
  --env-secret OPENAI_API_KEY --timeout 180 --repeat 5
```

**Look at the rate, not the verdict.** A single PASS from a model-backed
subject is close to meaningless; `--repeat 5` is the smallest sample that says
anything, and even that is thin. See
[running-it-yourself.md](running-it-yourself.md) for what it costs and what
bounds the spend.

**It is a bug if** the key appears anywhere in `evidence.json`. `--env-secret`
takes a *name*, and Beacon redacts the value wherever it appears.

---

## 8 · What to report

For anything that disagrees with this document, the most useful report is the
evidence bundle: `evidence.json` and `report.md` from the run, plus which
command you ran and on what OS and Python version.

A **wrong verdict** — Beacon saying PASS where the agent misbehaved, or FAIL
where it did not — is the most valuable bug this project can receive, and there
is an issue template for it. A verdict you merely disagree with is also worth
raising; the reasoning is in the bundle, so the disagreement can be settled
rather than argued.

Known and already recorded, so not worth reporting:

- Step 5 of the playground shows all three baselines regardless of which
  scenario you selected in steps 1–2.
- `site/TEST-PLAN.md` §1 describes the previous hero design.
- `docs/beacon-test-run.md` is a dated record from 2026-08-02 and its figures
  are the ones that were true then.
- `beaconlab.dev` does not resolve to this site yet.

---

## Time budget

| Section | Roughly |
|---|---|
| §1 the two gate commands | 4 min |
| §2 the CI mirror | 6 min |
| §3 packaging | 3 min |
| §4 the figures | 2 min |
| §5 falsification | 15 min |
| §6 site | 10 min, plus browser download |
| §7 a model | 5 min, or skip |

Under an hour for all of it. §1 and §5 are the two worth doing if you only have
twenty minutes: one tells you the project passes its own checks, and the other
tells you whether those checks mean anything.
