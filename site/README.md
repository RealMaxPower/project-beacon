# The Beacon site

A marketing site and an evidence playground, built from the design system in
[`design/`](design/).

Everything factual on these pages is generated from this repository or read out
of it. That is not a style preference — a marketing site is the largest surface
of unpinned claims this project will ever have, and the README already said
"twenty-one subjects" ten lines above its own "40/40 verdicts correct" for
longer than it should have. `tests/test_site_claims.py` is what stops the same
thing happening here.

## Running it

```bash
cd site
npm install
npm run dev
```

| Command | What it does |
|---|---|
| `npm run dev` | Vite dev server. |
| `npm run build` | Typecheck, then a static bundle in `dist/`. |
| `npm run smoke` | Render every screen headless against the recorded fixtures. |
| `npm run fixtures` | Re-record the runs the playground replays. |
| `npm run fixtures:check` | Re-run them and report whether anything moved. |

The Python side is unchanged by any of this. `site/tools/build_fixtures.py`
imports `beacon`, never the reverse, and `MANIFEST.in` prunes this directory —
`pip install project-beacon` carries no part of it.

## Where the data comes from

The playground replays real runs. `tools/build_fixtures.py` executes scenarios
against real subjects out of `examples/subjects/` and commits what Beacon wrote:

```text
src/data/generated/
  index.json          which demos exist, and what each one shows
  scenarios.json      the seven scenarios, read from scenarios/*/scenario.json
  baselines.json      the recorded multi-run measurements, from baselines/
  <demo>/evidence.json, events.json, report.md
```

Four of the five demos are adversarial subjects that already existed, chosen
because they produce the states the playground needs to show:

| Demo | Subject | Verdict |
|---|---|---|
| misbehaving | `attempts_send.py` | FAIL — a blocked send attempt |
| well behaved | `well_behaved.py` | PASS |
| follows the injection | `obeys_injection.py` | FAIL — obeys the payload in m-004 |
| host that disconnects | `never_completes.py` | INCOMPLETE |
| reference agent | in-process | PASS |

The only edit made to a recorded bundle is rewriting the recording machine's
repository path to `<repo>`, which is why that string appears in the recorded
command. `tests/test_site_claims.py` fails if a real home directory survives.

Two figures cannot be regenerated offline, because they need a hosted agent and
an API key: the twelve-run divergence and the baseline comparison. Those are
read from `baselines/*.json`, which the repository already commits.

## What is authored

`src/data/copy.ts`, and nothing else. It holds the plain-English question on
each scenario card, the sentence versions of assertion ids, and the empty-state
text. If a number ever appears in that file, it is in the wrong file — the test
suite checks for exactly that.

## Rules that are not style preferences

These are enforced by `tests/test_site_claims.py`, not by convention:

- **No certification language.** Not "certified", "verified safe", "approved" —
  in body copy, alt text, tooltips or page titles.
- **Limitations cannot be dismissed.** `LimitationsBlock` has no `onDismiss`
  and no collapsed variant. Limitations ship inside the evidence bundle, so they
  ship inside every surface that displays one, and the strings are the ones
  `beacon/runner.py` writes.
- **No social proof.** There is no logo wall, counter, testimonial or badge
  component, and the suite fails if one is added. Nothing to fill in later means
  no pressure to invent it.
- **Attempts render heavier than successes.** A blocked call is the primary
  evidence, not an error. Policy stops the send either way, so the end state is
  identical whether or not the agent tried — the attempt is the only thing that
  tells them apart.
- **Chrome never uses green, red or amber.** Those three belong to the verdicts.
  That includes the lighthouse gold the name suggests, which is INCOMPLETE's
  colour.

## Deploying

Vercel, root directory `site`, build `npm run build`, output `dist`. It builds
on Vercel's infrastructure, so no GitHub Actions minutes are billed and
`tests/test_workflow_cost.py` needs no exception. Do not add a deploy workflow:
that test fails any workflow with an uncommented `push:` trigger.

## Pages

Six marketing screens and the playground, on a hash router — no dependency, and
no rewrite rules needed from whatever serves the files.

| Route | What it is |
|---|---|
| `#/` | Home. The hero is a run that did not succeed. |
| `#/how-it-works` | The pipeline, and where evidence is collected. |
| `#/scenarios` | The seven, grouped by what they grade. |
| `#/for-builders` | `--repeat`, baselines, and failing CI on a regression. |
| `#/playground` | Replays the recorded runs. |
| `#/docs` | Cards generated from `docs/` and `conformance/`. |
| `#/hosted` | The commercial question, asked without a waitlist form. |

## Not built yet

A dedicated mobile treatment. The pages are responsive — fluid type, single
column under `sm`, tables that scroll inside their own container — but the
device-frame designs in `design/Beacon Mobile.dc.html` have not been built.
