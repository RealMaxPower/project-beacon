# Protocol contracts

## Beacon JSONL command bridge 0.1

The bridge transports normalized requests and events between Beacon and a
subject process. Each message is one UTF-8 JSON object followed by a newline.
The subject must reserve standard output for protocol messages; diagnostic
output belongs on standard error or in a `log` message.

### Beacon to subject

`start`

- `protocol_version`: bridge protocol version.
- `run_id`: opaque run identifier.
- `scenario`: public scenario description, goal, output contract, and limits.
- `tools`: MCP-shaped tool definitions, restricted to the scenario's surface.

`scenario.output_contract.artifact`, when present, names the artifact the
subject must return. It is sent because a requirement the subject is never told
is not a requirement it can meet. Assertions are never sent.

`tools` is authoritative. A subject should call only what it lists; anything
else is refused, recorded as an attempt, and does not reach a service.

`tool_result`

- `id`: matching tool-call identifier.
- `ok`: success flag.
- `result`: structured result when successful.
- `error`: structured type and message when unsuccessful.

### Subject to Beacon

`tool_call`

- `id`: unique call identifier.
- `tool`: exact declared tool name.
- `arguments`: JSON object satisfying the tool input schema.

`artifact`

- `name`: stable artifact identifier.
- `content`: any JSON value.

`log`

- `level`: diagnostic level.
- `message`: human-readable text.

`complete`

- `status`: normally `completed`; other values produce `INCOMPLETE`.
- `summary`: optional human-readable result.
- `metadata`: optional non-secret structured metadata.
- `error`: optional error summary.

## MCP support

The MVP client implements these MCP stdio methods:

- `initialize`
- `notifications/initialized`
- `tools/list`
- `tools/call`

It negotiates a protocol version and records server identity and capabilities.
It does not yet implement resources, prompts, roots, sampling, elicitation,
OAuth, Streamable HTTP, experimental MCP tasks, or server-originated requests.

Use a complete official MCP SDK when these features are added. The minimal
client is primarily a zero-dependency interoperability spike and fixture
harness.

## A2A support

The MVP client implements:

- Agent Card discovery at `/.well-known/agent-card.json`.
- Selection of a declared supported interface.
- A2A-Version negotiation header.
- `SendMessage` over HTTP+JSON/REST.
- `SendMessage` over JSON-RPC.

It does not yet implement streaming, task retrieval/listing, push
notifications, cancellation, extended Agent Cards, multiple-interface fallback,
JWS verification, or complete authentication negotiation.

Use an official A2A SDK when the scenario adapter is implemented. The current
client exists to validate Beacon's protocol-neutral boundary.

