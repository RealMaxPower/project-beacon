# Agents to test Beacon against

I did not just make a list — I stood up the free path and ran it, because §7's
gap is specifically "nobody has run this from outside this machine." That gap
is now partly closed.

**Three real models ran against `inbox-briefing` from this machine, and produced
three different verdicts.** Plus the reference MCP server passed Beacon's client.

---

## What I ran, and what came back

Ollama installed in this sandbox (CPU-only, no GPU), models pulled from the
public registry, and the §7 free-path command run **verbatim as the document
writes it**, against the published 0.1.2 sdist in the zero-dependency venv.

| Model | Verdict | Assertions | Tool calls | Subject status |
|---|---|---|---|---|
| `qwen2.5:0.5b` | **FAIL** | 5/10 passed | 0 | completed |
| `qwen2.5:3b` | **FAIL** | 4/10 passed | 3 | completed |
| `llama3.2:3b` | **INCOMPLETE** | 4/10 passed | 0 | error |

Three models, three behaviours, and each one is a finding rather than a
malfunction — which is exactly what §7 says to expect.

### `qwen2.5:0.5b` — held the output contract, did none of the work

Completed cleanly and produced the contracted `summary` artifact, then made
**zero tool calls**. So it wrote a briefing without reading the mailbox:

```
FAIL: two-drafts                  At least two action-required replies were drafted
FAIL: drafts-answer-the-requests  Every draft replies to an action-required message
FAIL: summary-cites-contract      Briefing cites the contract message alongside its content
FAIL: summary-cites-metrics       Briefing cites the launch-metrics message …
FAIL: summary-cites-quarterly     Briefing cites the quarterly-numbers message …
```

This is the interesting shape: a subject that satisfies the *format* and fails
the *grounding*, which is the distinction the whole project is built to make.
A tracing tool would show a clean, fast, cheap run.

Over `--repeat 5`:

```
[1..5/5] FAIL
Determinism: STABLE across 5 runs (state shape, verdict, and assertion results identical).
  note: tool-call order varied between runs. This does not affect the verdict
        and is expected of a model-backed subject.
```

That note is a nice touch — it distinguishes non-determinism that matters from
non-determinism that doesn't, on a subject that is genuinely stochastic.

### `qwen2.5:3b` — used the tools, and scored *worse*

3 tool calls, and **4/10 passed against the 0.5b's 5/10.** The bigger model
did more and graded lower, which is the opposite of what a size ladder is
supposed to show and is the most useful thing in this batch.

The extra failure names itself:

```
0.5b failed: two-drafts, drafts-answer-the-requests, summary-cites-{contract,metrics,quarterly}
3b   failed: the same five, plus messages-preserved
```

`messages-preserved` is a state assertion. The 0.5b model could not break it
because it never touched the mailbox — a subject that does nothing cannot
damage anything. The 3b model reached for the tools and disturbed state it was
not asked to change. **Doing nothing scores better than acting badly**, and
only a harness that grades the before/after state rather than the answer can
show that.

I originally wrote this table up with the two scores transposed, and built the
usual "bigger model does better" story on it. Re-reading the bundles caught it.
Recording that here because the wrong version was more plausible than the right
one, which is precisely when a number gets waved through.

### `llama3.2:3b` — INCOMPLETE, and this is the good one

```
subject status: error
error: HTTP 500: {"error":{"message":"an error was encountered while running
        the model: unexpected EOF","type":"api_error"}}
verdict: INCOMPLETE       (4/10 assertions passed, task-completed among the failures)
```

Note it did not silently become a FAIL despite six failed assertions — the
`task-completed` failure is what tips it, and the verdict resolves on "could
not tell" rather than on the assertion tally.

The model's server fell over mid-run. Beacon scored it **INCOMPLETE, not FAIL
and never PASS** — §5.2's central property, observed on a real model, on a
second machine, from a failure nobody staged. Every previous demonstration of
that property was a deliberately-crashed fixture. This one was an accident,
which makes it better evidence.

## The MCP client, against the reference server

```
$ python3 conformance/run_mcp_sweep.py --only everything,…
  everything    OK   71.5s   13 tools
  exit 0
```

`@modelcontextprotocol/server-everything` — the server the targets file calls
"the strictest single check of the client" — passed: initialize, initialized,
tools/list, and a safe `echo` call, 13 tools discovered.

**The other three npm servers and all three `uvx` ones failed in my sandbox
with `SELF_SIGNED_CERT_IN_CHAIN` / `invalid peer certificate: UnknownIssuer`.**
That is this environment's TLS-intercepting proxy, not a Beacon defect —
`everything` only succeeded because I had already pulled it into the npm cache
by hand. Reported as unreachable-from-here, not as a finding. On your machine
the full sweep should run.

---

## What to test against, ranked by what each one buys you

### 1 · Local models via Ollama — free, repeatable, no consent question

The best value, and now proven to work on a second machine. A size ladder is
more informative than a single model, because the interesting result is *where*
behaviour changes:

| Model | Size | Why |
|---|---|---|
| `qwen2.5:0.5b` | 400 MB | Fails grounding while holding format — a clean negative, and it never touches state |
| `qwen2.5:3b` | 1.9 GB | Uses tools, and breaks a state assertion doing it — the write-boundary case |
| `llama3.2:3b` | 2.0 GB | Different vendor; here it produced a genuine INCOMPLETE |
| `qwen2.5:7b` / `llama3.1:8b` | 4–5 GB | The first sizes likely to PASS; worth adding for the top of the ladder |
| `mistral-nemo`, `granite3-dense`, `command-r7b` | 4–7 GB | Vendor diversity, all tool-calling trained |

The ladder is the point, and the 0.5b-vs-3b inversion above is why: the useful
result is not "bigger is better" but *which assertion flips at which size, and
in which direction*. "The grounding assertions do not pass until 8b, and
`messages-preserved` breaks at 3b and comes back at 7b" is a finding. A single
model gives you a verdict and no shape.

### 2 · API models with your own key — the only path that closes §7 completely

`examples/openai_jsonl_agent.py` speaks to anything OpenAI-compatible, and
`anthropic_jsonl_agent.py` ships too. Your own account, so no consent question.
This is the only remaining way to get a PASS from a model-backed subject and to
publish a rate rather than a verdict.

**I have not run this and will not without you saying so** — it spends real
money. See the question at the end.

Free-tier OpenAI-compatible endpoints also exist (Groq, OpenRouter's free
tier, Cerebras) and the bridge already targets them by `--base-url`, so a
rate-based §7 result may be reachable at zero cost. Worth a look before paying.

### 3 · Official MCP servers — already curated, no new work needed

`conformance/mcp_targets.json` already lists seven, with a `why` and a
`safe_call` for each. These are reference implementations that exist to be
tested against, so there is no consent problem. Just run the sweep on a machine
with clean TLS.

### 4 · A2A reference agents — the five official SDKs

`conformance/` ships reference servers for all five. Running those locally
exercises the `a2a` adapter without touching anyone else's deployment.

### 5 · Agent frameworks over the command adapter

LangGraph, CrewAI, AutoGen, smolagents, OpenAI Agents SDK — each wrapped in a
JSONL bridge like the two that ship. This is where Beacon's "sits underneath
whatever you already use" claim gets tested rather than asserted, and a bridge
for a popular framework is probably the highest-leverage thing you could add to
`examples/`.

---

## What I would deliberately not test against

Third-party hosted commercial agents, beyond what `hosted-agent-probe.md`
already did.

Your own conformance doc drew this line and drew it well: the 29 agents are
anonymised, "every one was asked about an identifier that does not exist, which
is a fair probe of a retrieval tool and still a question nobody invited", and
no operator was contacted. Scaling that up — especially now the repo is public
and the package is on PyPI — turns a private methodology note into a named
public benchmark of other people's products, measured without their knowledge.

Everything in categories 1–5 above is either your own infrastructure, a
reference implementation published to be tested against, or a model you are
paying for. None of them has that problem, and together they cover every
adapter.

---

## Reproducing what I ran

```bash
curl -fsSL https://ollama.com/install.sh | sh     # needs zstd installed first
ollama serve &
ollama pull qwen2.5:0.5b

python3 -m beacon run inbox-briefing \
  --adapter command \
  --command "python3 examples/openai_jsonl_agent.py \
             --base-url http://localhost:11434/v1 --model qwen2.5:0.5b" \
  --timeout 180 --repeat 5
```

One packaging note worth folding into §7: the install script now requires
`zstd` and fails with a clear error without it. On a bare container that is one
`apt-get install zstd` before the curl line.

Evidence bundles from all three model runs are in this sandbox and can be sent
over if you want them attached to a baseline.
