# A2A conformance survey

Beacon's A2A client was written from the specification, then repaired against
four live agents that all speak 0.x. Its 1.x path had never met a 1.x server,
and its discovery had only ever been pointed at agents that serve the current
well-known path.

This survey went looking for the gaps. It found four defects, three of them
capable of reporting a working agent as broken.

## What was tested

| Target | How | Result |
|---|---|---|
| Official `a2a-sdk` 1.1.2, 1.0-only mode | local reference server | 3 defects |
| Official `a2a-sdk` 1.1.2, 0.3-compat mode | local reference server | same shapes |
| `web-page-extractor.fly.dev` | live, read-only | already worked |
| `searchopti.cloud` | live, read-only, 8 skills | already worked |
| `api.upmoltwork.mingles.ai` | live, discovery only | **undiscoverable** |
| `agent-chat.…azurecontainerapps.io` | live, discovery only | **undiscoverable** |

The last two were discovered but not driven. `UpMoltWork` publishes a
`task-marketplace` skill and `ConferenceHaven` publishes
`send_calendar_invite`; both can change someone's state, and neither belongs
to us. Fetching a card costs one request and is what the card is for. Sending
a message is not.

## Defects found

**A Message reply was reported as INCOMPLETE.** `message/send` may answer with
a Task or with a bare Message, and the SDK returns a Message for any agent
with no long-running work to track — the default shape for the simplest kind
of agent. Beacon read the missing task status as an unrecognised state and
resolved the run to INCOMPLETE, which in Beacon's own semantics means *did not
run*. The evidence said the opposite of what happened, and it would have said
it about every agent of that shape.

**The reply text was dropped.** Artifact extraction read `artifacts` and
`history`. A bare Message has neither, so a run that received a perfectly good
answer recorded no artifacts at all, and every content assertion failed for
want of anything to assert against.

**`ROLE_AGENT` was not recognised as the agent.** 1.x generates its wire
format from protobuf, where the enum member name is what lands in JSON. The
history filter matched only the 0.x spelling `agent`. The reference server
sends `ROLE_AGENT` even in its 0.3 compatibility mode, so this was not
confined to 1.x servers.

**The legacy Agent Card path was never tried.** The specification renamed
`/.well-known/agent.json` to `/.well-known/agent-card.json`. Deployed agents
did not all move. Both live public agents found in this survey answer 404 on
the new path and 200 on the old one, so Beacon could not see either, and
reported a 404 as though the agent did not exist. Discovery now tries both,
newest first — and only on a 404, since a 401 or a timeout is about that
endpoint and says nothing about where the card lives.

## Reproducing

```bash
pip install "a2a-sdk[http-server]" fastapi uvicorn
python3 conformance/a2a_reference_agent.py 8731        # 1.0 only
python3 conformance/a2a_reference_agent.py 8732 --v03  # + 0.3 methods

python3 -m beacon a2a-inspect http://127.0.0.1:8731 --send hello
python3 -m beacon run hosted-injection-resistance \
  --adapter a2a --agent-url http://127.0.0.1:8731
```

The echo agent is meant to FAIL the scenario — it does not summarise anything.
What matters is that the run completes, stores an artifact, and reaches a
verdict. Before these fixes it reached INCOMPLETE with nothing recorded.

The wire shapes the reference server produced are pinned in
`tests/test_a2a_response_shapes.py`, which needs no SDK and runs everywhere.
Re-run the server against a new SDK release to find out whether they still
hold.

## On finding public A2A agents

There are very few. The MCP registry lists hundreds of hosted servers; the A2A
equivalent does not meaningfully exist yet — `a2aregistry.org` renders its
listing client-side and serves the same HTML for every path, so there is no
index to fetch. A code search across public repositories for deployed card
URLs returned thousands of matches and eight distinct hosts, of which five
were placeholders (`ai.domain.com`, `agent.example`) and one was a dead
ngrok tunnel.

That scarcity is itself worth knowing: an A2A client cannot be hardened by
breadth of live traffic the way an MCP client can. The reference
implementation carries the weight instead, which is why it is committed here
rather than run once and thrown away.
