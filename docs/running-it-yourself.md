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

Copy [`.env.example`](../.env.example) to start from; it lists the three
variables that exist and says which of them you actually need.

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

Cursor, Claude Desktop, or anything else that speaks MCP and that you drive by
hand. Beacon serves the scenario's synthetic tools over loopback HTTP and waits
for the host to connect.

Loopback is the constraint that decides which hosts can do this without extra
work. A host whose MCP client runs on your machine — Cursor directly, Claude
Desktop through a stdio proxy — connects to `127.0.0.1` and is done. A host
that connects from a vendor's cloud, which is how Cowork, claude.ai and the
mobile apps add a remote server, needs a tunnel. See [Wiring it
up](#wiring-it-up) for both.

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

The façade is a Streamable HTTP MCP endpoint on **loopback**, with a bearer
token. That one word decides how each host connects, so it is worth stating
before the recipes: a host that runs its MCP client on your machine can reach
`127.0.0.1` directly, and a host that connects from somewhere else cannot.

The generated `mcp-config.json` is in the shape a local host expects:

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

**Cursor** reads `~/.cursor/mcp.json`. Merge the `mcpServers` entry in. Its
client runs locally, so loopback works and there is nothing else to do.

**Claude Desktop** speaks stdio to local servers, not HTTP, so it needs a
proxy in between. [`mcp-remote`](https://github.com/geelen/mcp-remote) is one,
and it runs on your machine, so the façade stays on loopback:

```json
{
  "mcpServers": {
    "beacon": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://127.0.0.1:8899/mcp",
        "--header",
        "Authorization:${AUTH_HEADER}"
      ],
      "env": { "AUTH_HEADER": "Bearer <token>" }
    }
  }
}
```

The missing space in `Authorization:${AUTH_HEADER}` is deliberate. Spaces
inside `args` are mangled when the config invokes `npx` on Windows, so the
space lives in the environment variable instead.

**Claude Desktop's *connector* settings will not work**, and neither will
Cowork, claude.ai, or the mobile apps. Those add a *remote* MCP server, and
Claude connects to one "from Anthropic's cloud infrastructure, rather than
from your local device" — so `127.0.0.1` is your machine, not theirs, and the
connection never arrives. This page said to use connector settings for longer
than it should have, which is the kind of claim the rest of this project
exists to catch.

To drive one of those, the façade has to be reachable from the public
internet, which means a tunnel:

```bash
cloudflared tunnel --url http://127.0.0.1:8899   # or: ngrok http 8899
```

Add the tunnel's `https://…/mcp` as a custom connector, with an
`authorization` request header whose value is `Bearer <token>` — the scheme
included, because the value is sent exactly as entered.

**Weigh that before doing it.** `SECURITY.md` lists loopback binding as a
control, and a tunnel removes it: the run's synthetic services become
reachable by anyone with the URL, and the per-run token is the only thing left
in front of them. The fixtures are synthetic and the token is fresh per run
unless you pinned it, so this is defensible for a scenario you are driving by
hand. It is not something to leave running.

Anything else: it is a Streamable HTTP MCP endpoint with a bearer token, and
the question to ask of it is where its client runs.

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
