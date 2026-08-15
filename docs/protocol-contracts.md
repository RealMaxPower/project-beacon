# Protocol contracts

## Beacon JSONL command bridge 0.2

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
is not a requirement it can meet.

Assertions and `metadata` are never sent. The rule is the same for both — a
subject that can read the grading is not being evaluated — but only assertions
were withheld at first. Metadata was where the authors left notes for each
other, and those notes came to name the file the exfiltration canary lived in
and the message carrying the injected payload. Nothing in metadata is a
requirement, so nothing in it is owed to the subject; it is recorded in the
evidence bundle instead, where the reader is not the thing being measured.

`tools` is authoritative. A subject should call only what it lists; anything
else is refused, recorded as an attempt, and does not reach a service.

Tool names must match `^[a-zA-Z0-9_-]{1,64}$`, checked when a service
registers. This is not Beacon's own rule: it is the constraint every surface
that publishes a tool set to a model applies — the Claude API's `tools`
parameter, and MCP names as a host republishes them. A dotted name is rejected
at the provider boundary, so the run fails on its first tool call rather than
producing a verdict. Namespace with underscores: `mail_list_messages`.

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

- `status`: how the subject is ending. See below.
- `summary`: optional human-readable result.
- `metadata`: optional non-secret structured metadata.
- `error`: optional error summary.

Three statuses are endings the subject *chose*, and they are handed to the
scenario's assertions to judge:

| `status` | Means |
|---|---|
| `completed` | Did the goal. |
| `input_required` | Stopped deliberately; needs something only a person can supply. Say what, in `summary`. |
| `declined` | Refusing the task. |

Anything else — including `failed` — is Beacon failing to observe a run, and
resolves to `INCOMPLETE` without consulting the assertions.

Only `completed` counted until bridge 0.2, which made stopping to ask a human
indistinguishable from crashing. That is the wrong answer for a harness whose
subject matter is restraint: an agent facing an ambiguous instruction or an
action over its authority is *supposed* to stop, and no scenario could say so.
A scenario that wants the task finished still says so with an assertion on
`subject.status`, and now gets `FAIL` rather than `INCOMPLETE` when a subject
escalates out of work it could have done.

## Beacon as an MCP server

`ScenarioMCPServer` serves a scenario's tool surface so any MCP host can be the
subject. Streamable HTTP on loopback, single endpoint `/mcp`, JSON-RPC over
POST, `application/json` responses. GET returns 405 — there is no
server-initiated stream. `Mcp-Session-Id` is returned on every response.

Implemented: `initialize`, `notifications/initialized`, `ping`, `tools/list`,
`tools/call`. Not implemented: resources, prompts, sampling, elicitation,
SSE streaming, resumability, OAuth. As with the client, use a complete MCP SDK
when those are needed; this exists to keep the core dependency-free and to
prove the boundary.

Every request must carry `Authorization: Bearer <token>` with the run's
ephemeral token, or the server answers 401.

`tools/list` returns the scenario's scoped tools plus one Beacon-provided tool:

`beacon_submit`

- `status`: `completed` or `failed`.
- `summary`: what the subject did.
- `artifact`: required when the scenario declares an output contract; recorded
  under the contracted artifact name.

This is the completion signal MCP does not otherwise have. A session that ends
without it resolves to `INCOMPLETE`.

A submission already received is not retracted by what happens afterwards. A
host that submits and then hangs past the timeout, or is stopped by hand, keeps
the verdict its submission earned — the same rule the JSONL bridge applies to
`complete`. Beacon terminating the host is recorded three ways: `timed_out` in
the `subject_completed` event, `terminated_after_complete` in the subject
metadata, and a limitation in `report.md`.

A failing tool call returns a normal `tools/call` result with `isError: true`,
never a JSON-RPC error — a refusal is information the subject can act on, and a
transport error is not. The attempt is recorded either way.

## MCP client support

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

