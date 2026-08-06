# Hosted MCP server survey

Beacon's MCP client against 200 hosted servers drawn from the official registry. One `initialize` and one `tools/list` each; no tool calls were made.

**The servers are not named here.** Each row is a real deployment, identified by
a stable pseudonym within this document. The reason is not doubt about the
measurements — it is that nobody asked to be measured, and none of these
operators were contacted before or after. A survey that publishes a named
server's error body alongside a defect count is a disclosure, and this one was
never run as a disclosure: it was run to harden a client. What hardens the
client is the distribution, which survives anonymisation intact.

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
| server-01 | 2.9 | 4 |
| server-02 | 2.7 | 9 |
| server-03 | 2.6 | 25 |
| server-04 | 2.6 | 12 |
| server-05 | 2.2 | 16 |

Under three seconds at the slowest. A handshake is not where the cost is.

## Failures worth reading

Endpoints are given by shape rather than by host, for the reason at the top.
The response bodies below are the servers' own, quoted only as far as the
failure mode needs.

| Server | Outcome | Detail |
|---|---|---|
| server-06 | unreachable | DNS did not resolve the registered host |
| server-07 | unreachable | DNS did not resolve the registered host |
| server-08 | unreachable | DNS did not resolve the registered host |
| server-09 | unreachable | DNS did not resolve the registered host |
| server-10 | unreachable | DNS did not resolve the registered host |
| server-11 | unreachable | DNS did not resolve the registered host |
| server-12 | unreachable | connection timed out |
| server-13 | unreachable | HTTP 522 — origin unreachable behind a CDN |
| server-14 | wrong-endpoint | HTTP 404, empty body |
| server-15 | wrong-endpoint | HTTP 405, empty body |
| server-16 | wrong-endpoint | HTTP 405 Method Not Allowed; registered over plain `http://` |
| server-17 | wrong-endpoint | HTTP 404 at the registered `/sse` path, HTML body |
| server-18 | wrong-endpoint | HTTP 404 at the registered `/sse` path, HTML body |
| server-19 | protocol-error | HTTP 530 — CDN error page, not the origin |
| server-20 | protocol-error | HTTP 500 `{"message": "Server Error"}` |
| server-21 | protocol-error | HTTP 200 with `content-type: text/html`, body opens `<!DOCTYPE html>` |
| server-22 | protocol-error | HTTP 400 `{"error":"Unsupported MCP-Protocol-Version: 2025-06-…"}` |
| server-23 | error | `InvalidURL: nonnumeric port: '{HAPI_PORT}'` |

Six of the eight unreachable servers are a registry entry whose hostname no
longer resolves — the registry records what was published, not what is still
running, and nothing prunes it.

`server-23` is the one worth keeping: the registry holds a URL with an
unsubstituted template variable in the port, `{HAPI_PORT}`, so the entry has
never been fetched by anything. It is not a server failing a handshake. It is
a published record that no client can have used, which is a different defect
and one that belongs to the registry rather than to the operator.

`server-21` is the common shape behind several of these: a 200 with an HTML
body. A client that checks status codes rather than parsing the body would
record it as a success.
