# Hosted MCP server survey

Beacon's MCP client against 50 hosted servers drawn from the official registry. One `initialize` and one `tools/list` each; no tool calls were made.

## Reachability

| Outcome | Servers |
|---|---|
| ok | 25 |
| auth-required | 22 |
| unreachable | 2 |
| protocol-error | 1 |

25 of 50 completed the handshake and returned a tool list, exposing 339 tools in total.

## Protocol versions negotiated

| Version | Servers |
|---|---|
| 2025-06-18 | 22 |
| 2025-03-26 | 2 |
| 2024-11-05 | 1 |

## Tool names that cannot be forwarded to a model

Names must match `^[a-zA-Z0-9_-]{1,64}$` to be published in an API `tools` parameter. Servers shipping names outside it cannot be relayed to a model without renaming.

None found in this sample.

## Slowest handshakes

| Server | Seconds | Tools |
|---|---|---|
| ai.marketintell/marketintell | 1.7 | 17 |
| ai.meacheal/mrc-data | 1.2 | 20 |
| ai.demanddiscovery/mcp | 0.9 | 10 |
| ai.kifly/mcp | 0.8 | 21 |
| ai.fodda/deep-research | 0.8 | 13 |

## Failures worth reading

| Server | Outcome | Detail |
|---|---|---|
| ai.baselight/baselight | unreachable | could not reach https://api.baselight.app/mcp: [Errno 8] nodename nor servname provided, or not known |
| ai.backengine/backengine-mcp | protocol-error | non-JSON response from https://backengine.ai/mcp (content-type 'text/html; charset=utf-8'): '<!DOCTYPE html>\n |
| ai.djwizard/tvwizard | unreachable | could not reach https://tv.djwizard.ai/mcp/: timed out |
