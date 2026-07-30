# A2A conformance survey

Beacon's A2A client was written from the specification, then repaired against
four live agents that all speak 0.x. Its 1.x path had never met a 1.x server,
and its discovery had only ever been pointed at agents that serve the current
well-known path.

This survey went looking for the gaps. All five official SDKs were run as
local servers, alongside three live deployments. Seven defects, five of which
would have reported a working agent as broken.

The shape of the results is the useful part:

| SDK | Defects |
|---|---|
| Python | 3 |
| JavaScript | 1 |
| Go | 1 |
| Java | 0 |
| .NET | 0 |

Three, then one, then one, then nothing twice. The first implementation
exposed how much of the client had only ever been read from the
specification; each one after found less, and the last two found nothing at all.
Two independent implementations agreeing that a client is correct is a
different claim from one implementation not having complained yet, and it is
the only evidence available that the earlier fixes were general rather than
patches shaped around a single library.

## What was tested

| Target | How | Result |
|---|---|---|
| Official `a2a-sdk` 1.1.2, 1.0-only mode | local reference server | 3 defects |
| Official `a2a-sdk` 1.1.2, 0.3-compat mode | local reference server | same shapes |
| Official `@a2a-js/sdk` 1.0.1 | local reference server | 1 defect |
| Official `a2a-go` v2.4.0 | local reference server | 1 defect |
| Official `a2a-java` 1.0.0.Alpha3 | local reference server | none |
| Official `A2A` .NET 1.0.0-preview2 | local reference server | none |
| `web-page-extractor.fly.dev` | live, read-only | already worked |
| `searchopti.cloud` | live, read-only, 8 skills | already worked |
| `api.upmoltwork.mingles.ai` | live, discovery only | **undiscoverable** |
| `agent-chat.…azurecontainerapps.io` | live, discovery only | **undiscoverable** |
| `agent.ai` | live, discovery only, auth-gated | **wrong transport** |

The last three were discovered but not driven. `UpMoltWork` publishes a
`task-marketplace` skill and `ConferenceHaven` publishes
`send_calendar_invite`; both can change someone's state, and neither belongs
to us. `agent.ai` is gated behind oauth2 or an API key. Fetching a card costs
one request and is what the card is for. Sending a message is not.

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

**A version declared only on the interface was ignored.** 1.x moved the protocol version into each `supportedInterfaces` entry, and an SDK that generates cards from the current schema need not emit the top-level field at all — the Go SDK does not. Beacon read only the top-level, so those cards fell back to the constructor default and an interface declaring 0.3 would have been answered with 1.x method names. The interface now wins, being the more specific claim: it describes the endpoint about to be called, where the top-level field describes the agent.

**The `A2A-Version` header contradicted the method name.** The method was chosen from the card while the header was a fixed `1.0`, so every 0.3 agent received a request whose header claimed 1.0 and whose body called `message/send`. Every server tested tolerated it by ignoring the header. The JavaScript SDK reads it, and answers the mismatched pair with `-32603 Cannot read properties of undefined` — an internal crash Beacon would have recorded as the agent failing, on a request Beacon malformed. The header now follows the card, at the major.minor granularity the header uses.

**The legacy Agent Card path was never tried.** The specification renamed
`/.well-known/agent.json` to `/.well-known/agent-card.json`. Deployed agents
did not all move. Both live public agents found in this survey answer 404 on
the new path and 200 on the old one, so Beacon could not see either, and
reported a 404 as though the agent did not exist. Discovery now tries both,
newest first — and only on a 404, since a 401 or a timeout is about that
endpoint and says nothing about where the card lives.

## Reproducing

Python SDK:

```bash
pip install "a2a-sdk[http-server]" fastapi uvicorn
python3 conformance/a2a_reference_agent.py 8731        # 1.0 only
python3 conformance/a2a_reference_agent.py 8732 --v03  # + 0.3 methods
```

JavaScript, Go, Java and .NET:

```bash
cd conformance/a2a-js     && npm install && npm start   # 8751
cd conformance/a2a-go     && go mod tidy && go run . 8771
cd conformance/a2a-java   && mvn quarkus:dev                # 8781
cd conformance/a2a-dotnet && dotnet run                     # 8791
```

Against either:

```bash
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

## Agent directories

Three were checked. Only one hosts a real A2A agent, and finding out which
took a request each — a directory of "AI agents" in the marketing sense lists
SaaS products with web UIs, which a protocol client cannot drive at all.

| Directory | Verdict |
|---|---|
| `agent.ai` | **A real A2A agent.** 0.3.0 card, 7 skills, oauth2/apiKey |
| `marketplace.kore.ai` | SPA catch-all — HTML for every path, including `/openapi.json` |
| `aiagentsdirectory.com` | SaaS product listings; 78 categories, none protocol-related |

The catch-all is worth calling out as a method note: `marketplace.kore.ai`
answers 200 to `/.well-known/agent-card.json`, `/.well-known/mcp.json` and
`/openapi.json` alike, and every one of them is the same HTML shell.
`a2aregistry.org` does the same. A status code proves nothing here; only
parsing the body does, which is why the sweep checks content rather than
reachability.

**agent.ai found the fifth defect.** Its card is 0.3.0 with a top-level `url`
and no `preferredTransport` at all. The specification declares
`@default "JSONRPC"` for that field; Beacon defaulted to the REST binding, so
an omitted transport produced `POST /message:send` against an agent that only
speaks JSON-RPC. That is the same failure that once made every deployed agent
unreachable, reached from a different direction — the earlier fix taught the
client to *read* `additionalInterfaces`, and left the default wrong.

## Can a marketplace supply more agents?

It was worth asking — agent.ai's own card claims thousands of agents — so both
marketplaces were followed to their listings.

**agent.ai routes everything through one door.** Its card carries a
non-standard `endpoint` field pointing at `https://mcp.agent.ai/mcp`, a
Streamable HTTP MCP server, and the description says each agent is exposed
"as a typed A2A skill and MCP tool". Beacon's MCP client reaches it and gets
a clean `HTTP 401 invalid_token`. Enumerating the catalogue needs an account.

**Kore's marketplace has no public listing.** It is an Angular application
whose bundle names `/marketplace/data` — a client-side route that returns the
shell — and an API at `/api/1.1/` that answers unauthenticated requests with
a JSON 404. Its agents run inside the Kore platform rather than as separately
addressable endpoints.

**And a marketplace is the wrong shape for this job anyway.** A protocol
client is hardened by *distinct implementations*, not by volume of traffic. A
thousand agents behind one gateway is one implementation of the protocol
exercised a thousand times: it would vary the content of the replies and
nothing about their shape. Every defect in this survey came from a different
implementation — the official Python SDK, a fly.io deployment, two servers on
the older card path, and agent.ai's card — and none of them came from
re-running an implementation already covered.

Where the diversity actually lives is the SDKs. Five official ones exist, each
written by different people from the same specification:

| SDK | |
|---|---|
| `a2aproject/a2a-python` | swept here, 3 defects |
| `a2aproject/a2a-js` | swept here, 1 defect |
| `a2aproject/a2a-go` | swept here, 1 defect |
| `a2aproject/a2a-java` | swept here, none |
| `a2aproject/a2a-dotnet` | swept here, none |

One of those five produced three defects in an afternoon. That is the seam to
keep pulling, and `conformance/a2a_reference_agent.py` is the template: stand
up the sample server, point Beacon at it, pin whatever shapes come back.

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
