# Hosted MCP server survey

Beacon's MCP client against 200 hosted servers drawn from the official registry. One `initialize` and one `tools/list` each; no tool calls were made.

## Reachability

| Outcome | Servers |
|---|---|
| ok | 98 |
| auth-required | 84 |
| unreachable | 8 |
| wrong-endpoint | 5 |
| protocol-error | 4 |
| error | 1 |

98 of 200 completed the handshake and returned a tool list, exposing 1364 tools in total.

## Protocol versions negotiated

| Version | Servers |
|---|---|
| 2025-06-18 | 83 |
| 2024-11-05 | 8 |
| 2025-03-26 | 7 |

## Tool names that cannot be forwarded to a model

Names must match `^[a-zA-Z0-9_-]{1,64}$` to be published in an API `tools` parameter. Servers shipping names outside it cannot be relayed to a model without renaming.

None found in this sample.

## Slowest handshakes

| Server | Seconds | Tools |
|---|---|---|
| ai.foura/mcp | 2.9 | 4 |
| ai.aviado/health | 2.7 | 9 |
| ac.inference.sh/mcp | 2.6 | 25 |
| ai.creativescope/creative-intelligence | 2.6 | 12 |
| ai.example4/xmp4 | 2.2 | 16 |

## Failures worth reading

| Server | Outcome | Detail |
|---|---|---|
| ai.baselight/baselight | unreachable | could not reach https://api.baselight.app/mcp: [Errno 8] nodename nor servname provided, or not known |
| ai.infolang/mcp | wrong-endpoint | HTTP 404 from https://api.infolang.ai/v1/mcp/:  |
| ai.lattiq/x402-trading-signals | protocol-error | HTTP 530 from https://api.lattiq.ai/mcp: {"type":"https://developers.cloudflare.com/support/troubleshooting/ht |
| ai.libers/libers-suite | protocol-error | HTTP 500 from https://api.libers.ai/mcp/libers-suite: {
    "message": "Server Error"
} |
| ai.conveo/conveo | unreachable | could not reach https://app.conveo.ai/api/mcp: [Errno 8] nodename nor servname provided, or not known |
| ai.backengine/backengine-mcp | protocol-error | non-JSON response from https://backengine.ai/mcp (content-type 'text/html; charset=utf-8'): '<!DOCTYPE html>\n |
| ai.biddeed/biddeed-mcp | wrong-endpoint | HTTP 405 from https://biddeed.ai/api/mcp:  |
| ai.biel/biel-ai | protocol-error | HTTP 400 from https://mcp.biel.ai/v2/{project_slug}/mcp: {"error":"Unsupported MCP-Protocol-Version: 2025-06-1 |
| ai.clarid/compliance | unreachable | could not reach https://mcp.clarid.ai/mcp: [Errno 8] nodename nor servname provided, or not known |
| ai.factori/mcp | unreachable | could not reach https://mcp.factori.ai/mcp: [Errno 8] nodename nor servname provided, or not known |
| ai.fiber/mcp | wrong-endpoint | HTTP 405 from http://mcp.fiber.ai/mcp/v2: Method Not Allowed |
| ai.fodda/mcp-server | wrong-endpoint | HTTP 404 from https://mcp.fodda.ai/sse: <!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title> |
| ai.matih/mcp | unreachable | could not reach https://mcp.matih.ai/api/v1/mcp: [Errno 8] nodename nor servname provided, or not known |
| ai.nashboard/nashboard-merchants | unreachable | HTTP 522 from https://nashboard.ai/mcp: {"type":"https://developers.cloudflare.com/support/troubleshooting/htt |
| ai.com.mcp/skills-search | unreachable | could not reach https://skills-sh.run.mcp.com.ai/mcp: [Errno 8] nodename nor servname provided, or not known |
| ai.intuitek.the-stall/the-stall | wrong-endpoint | HTTP 404 from https://the-stall.intuitek.ai/sse: <!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" |
| ai.djwizard/tvwizard | unreachable | could not reach https://tv.djwizard.ai/mcp/: timed out |
| ai.com.mcp/hapi-mcp | error | InvalidURL: nonnumeric port: '{HAPI_PORT}' |
