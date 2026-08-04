from __future__ import annotations

import ipaddress
import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

from beacon.protocols.mcp import MCPError


USER_AGENT = "project-beacon/0.1"
PROTOCOL_VERSION = "2025-06-18"
MAX_REDIRECTS = 3
# The origin the caller was pointed at, carried on the request so a redirect
# handler can tell a hop that stays home from one that leaves.
BASE_ORIGIN_ATTRIBUTE = "_beacon_base_origin"
# Mirrors the cap the server side applies in `mcp_server`: a stranger's server
# does not get to decide how much memory the harness allocates.
MAX_BODY_BYTES = 4 * 1024 * 1024


def _ssl_context() -> ssl.SSLContext | None:
    """Fall back to certifi when the interpreter ships no CA store."""
    paths = ssl.get_default_verify_paths()
    if paths.cafile or paths.capath:
        return None
    try:
        import certifi
    except ImportError:
        return None
    return ssl.create_default_context(cafile=certifi.where())


def _origin(url: str) -> tuple[str, str, int] | None:
    """
    The (scheme, host, port) a URL would be fetched from, or None if it is not
    fetchable over http(s) at all — a different scheme, or no host to talk to.

    The default port is filled in so that `https://host/` and `https://host:443/`
    compare equal, since credentials travel with the origin.
    """
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    return (parsed.scheme, parsed.hostname.lower(), port)


def _is_internal(host: str) -> bool:
    """
    Whether a host names an address that is not reachable from the public
    internet — loopback, RFC1918, link-local (including 169.254.169.254),
    and the other reserved ranges.

    Every address the name resolves to has to be public for the answer to be
    False, so a name that resolves to both a public and a private address is
    treated as private.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        # Unresolvable: the request will fail on its own, and refusing here
        # would turn a plain DNS failure into a security error.
        return False
    for info in infos:
        try:
            address = ipaddress.ip_address(info[4][0].split("%")[0])
        except ValueError:
            continue
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            return True
    return False


def _refuse_internal(base: tuple[str, str, int] | None, target: tuple[str, str, int]) -> bool:
    """
    Whether a hop from `base` to `target` reaches into the harness's own
    network.

    Only cross-origin hops are judged, and only when the operator did not aim
    Beacon somewhere internal to begin with: pointing it at a server on
    localhost is the ordinary way to test one, and that must keep working.
    """
    if base is not None and target == base:
        return False
    if base is not None and _is_internal(base[1]):
        return False
    return _is_internal(target[1])


class _PinnedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """
    Judge the redirects urllib follows on its own by the same rule as the
    307/308 hops the client follows by hand.

    Otherwise the check is one in name only: a registry-listed server answers
    with a 302 instead, and urllib follows it anywhere, copying every header
    across — Authorization included, since urllib does not strip credentials
    on a cross-host redirect.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        base = getattr(req, BASE_ORIGIN_ATTRIBUTE, None)
        target = _origin(newurl)
        if target is None:
            # Nothing else closes `fp` once this raises.
            fp.close()
            raise MCPError(f"refusing redirect to {newurl[:120]}")
        if _refuse_internal(base, target):
            fp.close()
            raise MCPError(
                f"refusing redirect to {newurl[:120]}: it resolves to an "
                f"address inside the harness's own network"
            )
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is None:
            return None
        setattr(new, BASE_ORIGIN_ATTRIBUTE, base)
        if base is None or target != base:
            for header in ("Authorization", "Mcp-Session-Id"):
                # urllib files header names `.capitalize()`d but matches
                # `remove_header` on the exact string, so "Mcp-Session-Id"
                # would silently fail to remove "Mcp-session-id".
                new.remove_header(header.capitalize())
        return new


def _build_opener() -> urllib.request.OpenerDirector:
    """
    An opener that can only speak http(s).

    `urlopen` uses the global opener, which carries file:, ftp: and data:
    handlers, so any URL that reaches it can read the local disk. Listing the
    handlers is the only way to *drop* one: `build_opener()` re-adds every
    default it was not handed a subclass of.
    """
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.ProxyHandler(),
        urllib.request.HTTPHandler(),
        urllib.request.HTTPSHandler(context=_ssl_context()),
        urllib.request.HTTPDefaultErrorHandler(),
        _PinnedRedirectHandler(),
        urllib.request.HTTPErrorProcessor(),
        urllib.request.UnknownHandler(),
    ):
        opener.add_handler(handler)
    return opener


def _parse_sse(payload: str) -> list[dict[str, Any]]:
    """
    Pull JSON-RPC messages out of an SSE body.

    Streamable HTTP lets a server answer a POST with either `application/json`
    or `text/event-stream`, and which one you get is the server's choice, not
    the client's. A client that only understands JSON silently fails against
    every server that picks the other.
    """
    messages: list[dict[str, Any]] = []
    data_lines: list[str] = []
    for line in payload.splitlines():
        if line.startswith("data:"):
            data_lines.append(line[5:].strip())
            continue
        if not line.strip() and data_lines:
            try:
                messages.append(json.loads("".join(data_lines)))
            except json.JSONDecodeError:
                pass
            data_lines = []
    if data_lines:
        try:
            messages.append(json.loads("".join(data_lines)))
        except json.JSONDecodeError:
            pass
    return messages


class MCPHTTPClient:
    """
    Minimal Streamable-HTTP MCP client, for servers hosted on the web.

    Beacon could only speak MCP over stdio, which meant every hosted server —
    the large majority of what is actually published — was unreachable. The
    surface here matches `MCPStdioClient` deliberately: initialize,
    tools/list, tools/call, and nothing else, so a caller can hold either.

    Sends no tool calls of its own. Inspecting a stranger's server should cost
    them one metadata request, not a side effect.
    """

    def __init__(
        self,
        url: str,
        *,
        timeout_seconds: float = 20.0,
        authorization: str | None = None,
        protocol_version: str = PROTOCOL_VERSION,
    ) -> None:
        if not url.startswith(("http://", "https://")):
            raise ValueError("MCP URL must use http or https")
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.authorization = authorization
        self.protocol_version = protocol_version
        self.session_id: str | None = None
        self.server_info: dict[str, Any] = {}
        self.capabilities: dict[str, Any] = {}
        self._request_id = 0
        # Pinned at construction: `self.url` moves as redirects are followed,
        # so it cannot answer "did this hop leave where the operator aimed?"
        self._base_origin = _origin(url)
        self._opener = _build_opener()

    def __enter__(self) -> "MCPHTTPClient":
        self.start()
        return self

    def __exit__(self, *_: Any) -> None:
        return None

    def _follow(self, location: str) -> None:
        """
        Move to a redirect target, or refuse to.

        Endpoint URLs come from a public registry, so the target is chosen by
        whoever registered the server. `urljoin` leaves an absolute URL with a
        different scheme untouched, which is what turns `Location: file:///…`
        into a local file read whose contents would be quoted back in the
        error text, and `Location: http://169.254.169.254/…` into a request
        the harness makes on the server's behalf. The bearer token and session
        id are the caller's, not the target's, so they travel only as far as
        the origin they were given for.
        """
        target = urllib.parse.urljoin(self.url, location)
        origin = _origin(target)
        if origin is None:
            raise MCPError(f"refusing redirect from {self.url} to {target[:120]}")
        if _refuse_internal(self._base_origin, origin):
            raise MCPError(
                f"refusing redirect from {self.url} to {target[:120]}: it "
                f"resolves to an address inside the harness's own network"
            )
        if origin != _origin(self.url):
            self.authorization = None
            self.session_id = None
        self.url = target

    def _read_body(self, response: Any) -> str:
        """
        Read a bounded amount of the response.

        The peer decides the length otherwise, and the sweep runs six of these
        at once. The declared length only saves the read; it is the peer's
        string, so it is trusted no further than "plainly a small number", and
        the capped read below is what actually holds for an undeclared or
        chunked body.
        """
        declared = response.headers.get("Content-Length", "").strip()
        if len(declared) <= 20 and declared.isascii() and declared.isdigit():
            if int(declared) > MAX_BODY_BYTES:
                raise MCPError(
                    f"response from {self.url} declares {declared} bytes, "
                    f"over the {MAX_BODY_BYTES} byte cap"
                )
        body = response.read(MAX_BODY_BYTES + 1)
        if len(body) > MAX_BODY_BYTES:
            raise MCPError(
                f"response from {self.url} is over the {MAX_BODY_BYTES} byte cap"
            )
        return body.decode("utf-8", "replace")

    def _post(self, message: dict[str, Any], _redirects: int = 0) -> dict[str, Any] | None:
        headers = {
            "Content-Type": "application/json",
            # Both are advertised because the server picks.
            "Accept": "application/json, text/event-stream",
            "User-Agent": USER_AGENT,
            "MCP-Protocol-Version": self.protocol_version,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        if self.authorization:
            headers["Authorization"] = self.authorization
        request = urllib.request.Request(
            self.url,
            data=json.dumps(message).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        setattr(request, BASE_ORIGIN_ATTRIBUTE, self._base_origin)
        try:
            with self._opener.open(request, timeout=self.timeout_seconds) as response:
                self.session_id = response.headers.get(
                    "Mcp-Session-Id", self.session_id
                )
                content_type = response.headers.get("Content-Type", "")
                body = self._read_body(response)
                status = response.status
        except urllib.error.HTTPError as exc:
            # urllib will not follow 307/308 for a POST, so a server that
            # redirects — to add a trailing slash, or to a canonical host —
            # looks unreachable rather than movable. These codes require the
            # method and body to be preserved, so following them is safe.
            if exc.code in {307, 308} and _redirects < MAX_REDIRECTS:
                location = exc.headers.get("Location")
                if location:
                    if exc.fp:
                        exc.close()
                    self._follow(location)
                    return self._post(message, _redirects + 1)
            detail = ""
            if exc.fp:
                detail = exc.read(300).decode("utf-8", "replace")
                exc.close()
            raise MCPError(
                f"HTTP {exc.code} from {self.url}: {detail[:200]}"
            ) from exc
        except urllib.error.URLError as exc:
            raise MCPError(f"could not reach {self.url}: {exc.reason}") from exc

        if status == 202 or not body.strip():
            return None
        if "text/event-stream" in content_type:
            messages = _parse_sse(body)
            if not messages:
                raise MCPError(f"no JSON-RPC message in the SSE body from {self.url}")
            return messages[-1]
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise MCPError(
                f"non-JSON response from {self.url} "
                f"(content-type {content_type!r}): {body[:160]!r}"
            ) from exc

    def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._request_id += 1
        message: dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
        }
        if params is not None:
            message["params"] = params
        response = self._post(message)
        if response is None:
            raise MCPError(f"no response to {method} from {self.url}")
        if "error" in response:
            raise MCPError(f"MCP error for {method}: {response['error']}")
        if "result" not in response:
            raise MCPError(f"MCP response for {method} omitted result")
        return response["result"]

    def notify(self, method: str) -> None:
        self._post({"jsonrpc": "2.0", "method": method})

    def start(self) -> None:
        result = self.request(
            "initialize",
            {
                "protocolVersion": self.protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "project-beacon", "version": "0.1.0"},
            },
        )
        negotiated = result.get("protocolVersion")
        if not negotiated:
            raise MCPError("MCP initialize response omitted protocolVersion")
        self.protocol_version = str(negotiated)
        self.server_info = dict(result.get("serverInfo", {}))
        self.capabilities = dict(result.get("capabilities", {}))
        try:
            self.notify("notifications/initialized")
        except MCPError:
            # Some servers reject the notification but work regardless; the
            # handshake has already succeeded by this point.
            pass

    def list_tools(self) -> list[dict[str, Any]]:
        result = self.request("tools/list", {})
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            raise MCPError("tools/list result must contain a tools array")
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self.request(
            "tools/call", {"name": name, "arguments": arguments}
        )
        if not isinstance(result, dict):
            raise MCPError("tools/call result must be an object")
        return result
