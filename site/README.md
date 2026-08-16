# The Beacon site

A marketing site and an evidence playground. It was built from a supplied
design mock whose export files are not in this repository: they carried a
design tool's runtime and a copied starter component, neither of which came
with a licence, and this repository cannot redistribute what it cannot
attribute. The visual system they defined lives in
[`src-b/tokens-b.css`](src-b/tokens-b.css), which is where it is now
maintained.

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
  scenarios.json      every shipped scenario, read from scenarios/*/scenario.json
  baselines.json      the recorded multi-run measurements, from baselines/
  <demo>/evidence.json, events.json, report.md
```

Most of the demos are adversarial subjects that already existed, chosen
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
on Vercel's infrastructure, so there is no deploy workflow here. Do not add
one: `tests/test_workflow_triggers.py` is default-deny on workflow files, and a
new one fails the suite until someone classifies what may start it.

## Pages

One long marketing page, the playground, and two screens, each prerendered to
its own document. `tools/prerender.tsx` writes them; `src-b/pages.ts` is the
table it, `sitemap.xml` and the structured data all read, so a page cannot
exist in one and be missing from the others.

| Route | What it is |
|---|---|
| `/` | The case, how it grades, your stack, what exists, quickstart, CI, questions. |
| `/playground` | Replays the recorded runs. |
| `/playground/<scenario>` | One per scenario, opened on it. |
| `/docs` | Cards generated from `docs/` and `conformance/`. |
| `/legal` | Licence, third-party notices, and what this site collects. |

These were fragments — `#/docs` — until it became clear what that cost. A
fragment is never sent to a server, so every screen was the same URL as far as
anything indexing was concerned, and the pages rendered in the browser, so a
crawler that runs no JavaScript received an empty `<div>`. Both are fixed by
the same change, and `tests/test_site_seo.py` is what stops them coming back.

Every page is also served as markdown at the same path with `.md` on it, and
`/llms.txt` indexes them. Same content, generated in the same pass, checked
against the HTML by `tests/test_site_markdown.py` — no User-Agent is consulted
anywhere, which is the difference between an alternate format and a private
edition for machines.

## Not built yet

A dedicated mobile treatment. The pages are responsive — fluid type, single
column under `sm`, tables that scroll inside their own container — but nothing
has been built specifically for a device frame.
