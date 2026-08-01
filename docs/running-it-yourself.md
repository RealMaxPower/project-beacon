# Running the two things Beacon cannot run for itself

Everything else in this repository runs headless and in CI. These two need a
person: one because it spends money, one because it involves a window.

## A real model as the subject

Beacon has no model in it. The bridge in `examples/` is just another external
subject, so the key is yours and the spend is yours.

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...

python3 -m beacon run inbox-briefing \
  --adapter command \
  --command "python3 examples/anthropic_jsonl_agent.py" \
  --env-secret ANTHROPIC_API_KEY \
  --timeout 180 \
  --repeat 5
```

**The key goes in your environment, never on the command line.** `--env-secret`
takes a *name*: Beacon reads the value from its own environment, passes it to
the subject, and removes it from the evidence bundle wherever it appears. The
command line itself is written verbatim into `evidence.json`, so a key typed
there would be published in the artifact you share.

A `.env` file works too — it is gitignored, and nothing in Beacon reads it, so
load it yourself first:

```bash
set -a && source .env && set +a
```

`BEACON_MODEL` picks the model; it defaults to `claude-sonnet-5`. Start with
`--repeat 1` to confirm the wiring before paying for five.

**What it will cost.** `inbox-briefing` is a handful of tool calls and a short
briefing — cents per run at Sonnet prices, not dollars. `--repeat 5` is the
smallest sample that says anything, and even that is thin: twelve runs of
`web-extraction-contract` against a real model put contract adherence at 2/12,
and any five of those could have read as 0/5 or 2/5.

Three things bound the spend, and it is worth knowing which. The scenario's
`timeout_seconds` and `max_protocol_messages` are enforced by the adapter, and
the bridge stops itself after `MAX_TURNS` model calls — 24 by default, edit it
if you want a tighter leash. `max_subject_calls` is **not** one of them here:
it counts requests Beacon makes *to* a subject, which is how a hosted agent is
driven, and a command subject drives itself. This paragraph used to cite it,
which was the wrong control for the command on this page.

**What to look at afterwards.** Not the verdict — the rate:

```
Determinism: DIVERGENT across 5 runs.
  verdicts: PASS 4 (80%), FAIL 1 (20%)
  flaky: summary-cites-contract passed 4/5 (80%) — failed on run-003
```

That is the number the whole project exists to produce. A single PASS from a
model-backed subject is close to meaningless.

## A GUI host as the subject

Claude Desktop, Cursor, or anything else that speaks MCP and that you drive by
hand. Beacon serves the scenario's synthetic tools over loopback HTTP and waits
for the host to connect.

```bash
export BEACON_MCP_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

python3 -m beacon serve-mcp inbox-briefing \
  --port 8899 \
  --token-env BEACON_MCP_TOKEN \
  --timeout 900
```

It prints the URL, the goal, and the path to a ready-made config file:

```
MCP server: http://127.0.0.1:8899/mcp
Config:     .beacon/runs/<run>/workspace/mcp-config.json
Goal:       Review the visible inbox. …
```

`--port` and `--token-env` exist for exactly this. Without them both change
every run, so the connector you saved in the GUI is stale before the second
run starts. Pinning them is opt-in: the default stays ephemeral, because a
fixed token is a weaker token and only a hand-configured host needs one.

### Wiring it up

The generated `mcp-config.json` is already in the shape most hosts expect:

```json
{
  "mcpServers": {
    "beacon": {
      "type": "http",
      "url": "http://127.0.0.1:8899/mcp",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
```

- **Cursor** reads `~/.cursor/mcp.json`. Merge the `mcpServers` entry in.
- **Claude Desktop** takes a remote MCP server through its connector settings;
  point it at the URL and supply the same bearer token.
- Anything else: it is a Streamable HTTP MCP endpoint with a bearer token.

Then paste the printed goal into the host and let it work. **The agent must
call `beacon_submit` when it is finished** — that tool is what ends the wait
and produces a verdict.

### Why it will say INCOMPLETE if you close the window

Beacon cannot see a GUI host start, so it cannot tell "still thinking" from
"gave up". A timeout or a Ctrl-C resolves INCOMPLETE, and evidence is still
written. That is not a limitation being apologised for — it is the rule that
"not run" is never a pass, applied to the one subject that cannot be observed
properly.

### If you are pairing with an assistant on this

The split that works: you run the command and connect the GUI, since neither
can be automated from outside. Then hand over the evidence path. Everything
after that — reading the bundle, comparing against a baseline, working out
which assertion moved — is offline work on files that are already written, and
needs no access to your machine or your account.
