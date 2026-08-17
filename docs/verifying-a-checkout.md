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

### Two things that will look like damage and are not

**A clone you do not own.** If the checkout belongs to another user, git
refuses it (`detected dubious ownership`) and the git-backed tests fail with a
message about untracked files rather than about ownership. Settle it first:

```bash
git config --global --add safe.directory "$(pwd)"
```

**§1 used to leave the tree dirty.** `tests/test_site_claims.py` regenerates the
site fixtures against the real working tree, so running the suite rewrote
committed files. The fixtures were pinned to the machine that recorded them —
the interpreter's absolute path in `command[0]`, and a traceback rendered
differently by each CPython version. Both are gone, so a regeneration here
should reproduce what was committed there.

The property that matters is **cross-machine**: regenerate on your machine,
compare against what the repository committed. Same-machine idempotence — run
the builder twice, get the same bytes — held even while this was broken, so it
is not evidence of anything. If `git status` is dirty after §1, that is the
real check failing, and it is worth reporting.

**§1 also depends on §6 having been run at least once.** Ten checks that read
the built site skip on a fresh clone, and the suite reports `OK (skipped=10)`
rather than naming them. That is expected; building the site in §6 and
re-running §1 turns them on.

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
OK                        # or OK (skipped=10) before §6 has built the site
```

```
415/415 verdicts correct.
```

Together they take about two and a half minutes — roughly 2m05 for the suite
and 28s for the subjects. The second prints a line per subject; the last line
is the one that matters.

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

**Watch the coverage pair.** `coverage run … -m unittest` carries the suite's
own exit status, and `coverage report --fail-under=80` does not: a red suite
still prints 88% and exits 0 from the second command. Read the first command's
result, or chain them with `&&`, or you can pass §2 with a failing §1.

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

Note that this installs the project into your *current* environment. §3 below
builds its own venv and does not use it, so the order is harmless — but if you
care about a pristine shell, do §3 first.

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
Failure taxonomy 1.2.0 (<path>/taxonomy/failure-modes.json)
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
rm -rf /tmp/vfy          # or B below becomes two paths on a second run
python3 -m beacon run inbox-briefing --output /tmp/vfy
B=$(ls -dt /tmp/vfy/*/ | head -1)evidence.json
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

Expect `The policy holds on every page.`, `No layout problems found across 12
pages × 5 widths.`, and `The playground reaches a verdict.`

`flow.mjs` will report `firefox is not installed; skipping` and the same for
webkit, because the install line above asks only for chromium. That is
expected. Install all three if you want the full sweep.

**It is a bug if** `visual` reports anything at 320px. It reported 16px of the
header's *Source* button hidden with no scroll cue on Linux, where Archivo's
fallback metrics run wider than on macOS — the same layout passed on one
machine's fonts and failed on another's. The wordmark is hidden below 360px
now, which buys 107px. A report there means the margin has been eaten again.

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

That wiring has been exercised against a stub endpoint on the author's machine:
the command shape above produced an artifact under the contracted name, carried
the reported token counts into the bundle, and reached a real verdict. **What
nobody has verified from outside is this section with an actual model behind
it** — every other section of this document has been walked on a second machine
and this one has not. If you run it, that gap is worth closing.

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

Seven bugs that earlier passes of this document found have been fixed, and are
listed because finding them again would waste your time. If any reappears, it
is a regression rather than a discovery, and worth saying so.

1. Fixtures pinned to the recording machine — its interpreter path in
   `command[0]`, and a traceback rendered differently by each CPython version.
   Broke `npm run check` for everyone who was not the author.
2. A doc shipped without its site description, so the docs page would have
   rendered a fallback blurb.
3. `DeepStructureTests` at a depth unreachable on Python 3.11, where the
   fixture died before reaching the code under test.
4. Two of those tests asserting only that files exist — true of every
   INCOMPLETE run, including one that crashed on its first line.
5. The 320px header, which clipped its own *Source* button wherever the font
   rendered a few pixels wider.
6. A test reading `site/dist/index.html` with no skip guard. This is the most
   likely of the seven to recur: `site/dist/` is gitignored, §1 runs before §6
   builds it, and the error is invisible to anyone whose checkout has ever been
   built — which always includes whoever wrote the test.
   `tests/test_site_claims.py` now fails if a module reads the built site
   without being able to skip when it is absent.
7. A 29 MB tarball committed to history by a `git add -A` that swept up a
   sandbox working folder. `_to_delete/` is gitignored for that reason.

---

## Time budget

| Section | Roughly |
|---|---|
| §1 the two gate commands | 2m30 |
| §2 the CI mirror | 6 min |
| §3 packaging | 3 min |
| §4 the figures | 2 min |
| §5 falsification | 15 min |
| §6 site | 20s for `check`; minutes more if Playwright has to download |
| §7 a model | 5 min, or skip |

Well under an hour for all of it — the commands are fast, and anything that
takes real time is a failure you are investigating. §1 and §5 are the two worth doing if you only have
twenty minutes: one tells you the project passes its own checks, and the other
tells you whether those checks mean anything.
