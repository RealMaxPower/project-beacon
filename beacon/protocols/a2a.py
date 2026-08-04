from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Sequence


class A2AError(RuntimeError):
    """Raised when an A2A endpoint cannot complete an operation."""


USER_AGENT = "project-beacon/0.1"

JSONRPC_METHODS = {
    # A2A 0.x, which is what deployed agents actually speak.
    "0": "message/send",
    # A2A 1.x renamed the JSON-RPC methods.
    "1": "SendMessage",
}

DEFAULT_PORTS = {"http": 80, "https": 443}
"""The schemes Beacon will speak to an agent over, and their default ports."""

ALLOW_ORIGIN_FLAG = "--allow-agent-origin"
"""The operator's opt-in, named in the refusal so the way forward is visible."""

ORIGIN_POLICY_ATTRIBUTE = "_beacon_origin_policy"
"""
Where the policy rides on the Request object.

The redirect handler is given only the request, so the policy has to travel
with it; a request that arrives without one is refused rather than followed.
"""


def _origin(url: str) -> tuple[str, str, int] | None:
    """
    Reduce a URL to the (scheme, host, port) triple that identifies its origin.

    Anything that is not http or https with a host has no origin at all, and
    None is returned: `file:`, `ftp:` and `data:` can then never match an
    allowed origin, whatever the operator typed.

    The port is always explicit, so `https://host:443` and `https://host` are
    one origin while `http://host:0` — which a card can write to smuggle past
    a naive `port or default` — is not `http://host`.
    """
    try:
        parsed = urllib.parse.urlsplit(url)
        port = parsed.port
    except ValueError:
        # A malformed authority: an unbracketed IPv6 address, a port that is
        # not a number or is out of range.
        return None
    scheme = parsed.scheme.lower()
    if scheme not in DEFAULT_PORTS:
        return None
    host = (parsed.hostname or "").lower()
    if not host:
        return None
    return (scheme, host, DEFAULT_PORTS[scheme] if port is None else port)


def _format_origin(origin: tuple[str, str, int]) -> str:
    scheme, host, port = origin
    if port == DEFAULT_PORTS[scheme]:
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


class _OriginPolicy:
    """
    Which origins Beacon may open a socket to, and which one holds the token.

    The Agent Card is data published by the party under evaluation, and the
    interface URL inside it is where `message/send` is POSTed — with the
    operator's Authorization header attached. Adopted verbatim, that lets the
    evaluated party choose the scheme, host and port of a credentialed request
    made from the operator's machine: a collector that harvests the bearer
    token, a plaintext downgrade, an address only the CI runner can reach, or
    a `file:` URL that reads local JSON into the run.

    So a card may only move Beacon within origins the operator named, and the
    credential is attached to the base URL's origin and to nothing else.
    """

    def __init__(self, base_url: str, allowed_origins: Sequence[str] = ()) -> None:
        base = _origin(base_url)
        if base is None:
            raise ValueError(f"A2A base URL has no http or https origin: {base_url}")
        self.base_origin = base
        self.allowed = {base}
        for extra in allowed_origins:
            origin = _origin(extra)
            if origin is None:
                raise ValueError(
                    f"an allowed A2A origin must be an http or https URL: {extra}"
                )
            self.allowed.add(origin)

    def check(self, url: str) -> tuple[str, str, int]:
        """Return the origin of `url`, or raise before anything is opened."""
        origin = _origin(url)
        if origin is None:
            raise A2AError(
                f"refusing to request {url}: an A2A endpoint must be an http "
                f"or https URL"
            )
        if origin not in self.allowed:
            raise A2AError(
                f"refusing to request {url}: {_format_origin(origin)} is not "
                f"{_format_origin(self.base_origin)}, and the Agent Card does "
                f"not get to choose where Beacon sends the operator's "
                f"credential; pass {ALLOW_ORIGIN_FLAG} "
                f"{_format_origin(origin)} to permit it"
            )
        return origin

    def carries_credential(self, url: str) -> bool:
        """
        Whether the Authorization header belongs on a request to `url`.

        Only the origin of the operator's own base URL. An extra origin the
        operator allowed is somewhere Beacon may reach, not somewhere the
        operator's token was issued for.
        """
        return _origin(url) == self.base_origin


class _PinnedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """
    Run every redirect hop through the same policy as the first request.

    Checking only the URL Beacon chose would be a check in name only: an
    allowed host answers with a 302 to anywhere, and urllib follows it,
    copying every header across — Authorization included, since urllib does
    not strip credentials on a cross-host redirect.

    The credential is re-attached exactly when the hop lands back on the base
    origin. Dropping it on every redirect instead looks safe and is not: an
    auth-gated card behind an ordinary same-origin 301 then gets an
    unauthenticated retry, and the agent reads as refusing Beacon.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        policy = getattr(req, ORIGIN_POLICY_ATTRIBUTE, None)
        if policy is None:
            # Fail closed. Nothing else closes `fp` once this raises.
            fp.close()
            raise A2AError(
                f"refusing to follow a redirect to {newurl}: the request "
                f"carries no origin policy"
            )
        try:
            policy.check(newurl)
        except A2AError:
            fp.close()
            raise
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is None:
            return None
        setattr(new, ORIGIN_POLICY_ATTRIBUTE, policy)
        authorization = req.get_header("Authorization")
        new.remove_header("Authorization")
        if authorization and policy.carries_credential(newurl):
            new.add_header("Authorization", authorization)
        return new


def _ssl_context() -> ssl.SSLContext | None:
    """
    Build a verifying SSL context, falling back to certifi when the interpreter
    has no CA store.

    A python.org install on macOS ships with an empty OpenSSL cert directory
    until `Install Certificates.command` is run, so every https request fails
    with CERTIFICATE_VERIFY_FAILED and looks like the remote agent is broken.
    Verification is never disabled — if there is no usable store, the error is
    allowed through so it can be read and fixed.
    """
    paths = ssl.get_default_verify_paths()
    if paths.cafile or paths.capath:
        return None
    try:
        import certifi
    except ImportError:
        return None
    return ssl.create_default_context(cafile=certifi.where())


def _build_opener() -> urllib.request.OpenerDirector:
    """
    Assemble the handler chain by hand, holding no handler Beacon cannot use.

    `build_opener()` will not do: it re-adds every default handler it was not
    passed a subclass of, and FileHandler and FTPHandler are among them — so
    an Agent Card naming `file:///etc/passwd` would still be opened by a chain
    that was meant to be locked down. Only http, https and the unknown-scheme
    handler that turns anything else into a clean error are registered.
    """
    opener = urllib.request.OpenerDirector()
    for handler in (
        urllib.request.ProxyHandler(),
        urllib.request.UnknownHandler(),
        urllib.request.HTTPHandler(),
        urllib.request.HTTPSHandler(context=_ssl_context()),
        urllib.request.HTTPDefaultErrorHandler(),
        urllib.request.HTTPErrorProcessor(),
        _PinnedRedirectHandler(),
    ):
        opener.add_handler(handler)
    return opener


def _open(request: urllib.request.Request, *, timeout: float) -> Any:
    """
    The one place an A2A socket is opened, so the policy cannot be bypassed.

    Every request goes through here, and the tests patch this seam.
    """
    return _build_opener().open(request, timeout=timeout)


class A2AClient:
    """
    Small A2A v1.0 discovery and HTTP+JSON client.

    It is sufficient for Beacon adapter spikes, not a complete A2A SDK.
    """

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 10,
        protocol_version: str = "1.0",
        authorization: str | None = None,
        allowed_origins: Sequence[str] = (),
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("A2A base URL must use http or https")
        self.base_url = base_url.rstrip("/")
        self.allowed_origins = tuple(allowed_origins)
        # Fixed at construction, from what the operator passed and nothing the
        # remote party will later say.
        self._policy = _OriginPolicy(self.base_url, self.allowed_origins)
        self.timeout_seconds = timeout_seconds
        self.protocol_version = protocol_version
        self.authorization = authorization
        self.agent_card: dict[str, Any] | None = None
        # Which well-known path actually answered, for the evidence record.
        self.card_url_used: str | None = None

    WELL_KNOWN_PATHS = (
        "/.well-known/agent-card.json",
        "/.well-known/agent.json",
    )
    """
    Where an Agent Card may live, newest first.

    The specification renamed this path: 0.2.x published `agent.json` and
    later revisions publish `agent-card.json`. Deployed agents did not all
    move, and two of the live public agents found in a survey answer 404 on
    the new path and 200 on the old one. Trying only the current name makes
    an entire generation of running agents invisible, and the failure reads
    as "no such agent" rather than "we looked in one place".
    """

    @property
    def card_url(self) -> str:
        if self.base_url.endswith(".json"):
            return self.base_url
        return f"{self.base_url}{self.WELL_KNOWN_PATHS[0]}"

    def _card_urls(self) -> tuple[str, ...]:
        if self.base_url.endswith(".json"):
            return (self.base_url,)
        return tuple(f"{self.base_url}{path}" for path in self.WELL_KNOWN_PATHS)

    def _target_origin(self, url: str) -> tuple[str, str, int]:
        """
        The origin `url` would be requested from, refused if unallowed.

        Discovery URLs are built from the operator's own base URL and always
        pass; the URL that has to be checked is the one `send_message` takes
        from the Agent Card, which is written by the party under evaluation.
        """
        return self._policy.check(url)

    def _request(
        self,
        url: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        content_type: str = "application/json",
        version: str | None = None,
    ) -> dict[str, Any]:
        # First, before a header is built or a socket is opened.
        self._target_origin(url)
        headers = {
            "Accept": "application/a2a+json, application/json",
            "A2A-Version": version or self.protocol_version,
            # Agents behind a WAF reject the default Python-urllib agent with
            # a 403, which reads as "the agent refused" rather than "we were
            # filtered". Identify ourselves.
            "User-Agent": USER_AGENT,
        }
        data = None
        if body is not None:
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = content_type
        if self.authorization and self._policy.carries_credential(url):
            headers["Authorization"] = self.authorization
        request = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method=method,
        )
        # The redirect handler sees only the request, so the policy travels
        # with it rather than being looked up from anywhere global.
        setattr(request, ORIGIN_POLICY_ATTRIBUTE, self._policy)
        try:
            with _open(request, timeout=self.timeout_seconds) as response:
                payload = response.read().decode("utf-8")
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            raise A2AError(f"A2A request failed for {url}: {exc}") from exc
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise A2AError(f"A2A endpoint returned invalid JSON for {url}") from exc
        if not isinstance(value, dict):
            raise A2AError(f"A2A endpoint returned a non-object for {url}")
        return value

    def discover(self) -> dict[str, Any]:
        """
        Fetch the Agent Card, trying each well-known path in turn.

        Only a 404 moves on to the next path. A 401, a 403 or a timeout is
        about *this* endpoint and says nothing about where the card lives, so
        retrying elsewhere would replace an accurate error with a misleading
        one about a path the agent never claimed to serve.
        """
        urls = self._card_urls()
        last: A2AError | None = None
        for index, url in enumerate(urls):
            try:
                card = self._request(url)
            except A2AError as error:
                if index + 1 < len(urls) and "404" in str(error):
                    last = error
                    continue
                raise
            self.card_url_used = url
            self.agent_card = card
            return card
        raise last or A2AError(f"no Agent Card found under {self.base_url}")

    def _interface(self) -> dict[str, Any]:
        """
        Pick the interface to talk to, across both card generations.

        1.x cards list `supportedInterfaces`. 0.x cards put the primary
        endpoint in `url` with a `preferredTransport`, and alternatives in
        `additionalInterfaces`. Reading only the 1.x field makes a 0.x card
        look like it declares nothing, and the client silently falls back to
        the REST binding — which is how a JSON-RPC agent ends up being sent a
        POST to `/message:send` that it has never heard of.
        """
        card = self.agent_card or self.discover()

        interfaces = card.get("supportedInterfaces")
        if isinstance(interfaces, list) and interfaces:
            interface = interfaces[0]
            if isinstance(interface, dict) and interface.get("url"):
                return interface

        if card.get("url"):
            return {
                "url": card["url"],
                # The specification declares `@default "JSONRPC"` for an
                # omitted preferredTransport, and omitting it is common —
                # agent.ai's live card does. Defaulting to the REST binding
                # instead sends `POST /message:send` to an agent that only
                # speaks JSON-RPC, which is the same failure that made every
                # deployed agent unreachable before, reached another way.
                "transport": card.get("preferredTransport") or "JSONRPC",
                "protocolVersion": self._card_protocol_version(),
            }

        additional = card.get("additionalInterfaces")
        if isinstance(additional, list) and additional:
            interface = additional[0]
            if isinstance(interface, dict) and interface.get("url"):
                return interface

        raise A2AError("Agent Card does not declare a supported interface URL")

    def _negotiated_version(self) -> str:
        """
        The value for the `A2A-Version` header, taken from the card.

        It used to be a fixed "1.0" while the *method name* was chosen from
        the card, so a 0.3 agent received a request whose header claimed 1.0
        and whose body used `message/send`. Every agent tested tolerated the
        contradiction by ignoring the header; the JavaScript SDK reads it, and
        answers a mismatched pair with an internal error — which would have
        been recorded as the agent failing, on a request Beacon malformed.

        Reported as major.minor, which is the granularity the header uses:
        a card saying "0.3.0" negotiates "0.3".
        """
        parts = self._card_protocol_version().split(".")
        return ".".join(parts[:2]) if len(parts) >= 2 else self.protocol_version

    def _card_protocol_version(self) -> str:
        """
        The protocol version the agent claims, wherever it chose to say it.

        1.x moved the statement into each entry of `supportedInterfaces`, and
        an SDK that generates cards from the current schema may not emit the
        top-level field at all — the Go SDK does not. Reading only the
        top-level meant those cards silently fell back to the constructor
        default, so an interface declaring 0.3 was answered with 1.x method
        names.

        The interface wins because it is the more specific claim: it
        describes the endpoint about to be called, where the top-level field
        describes the agent as a whole.
        """
        card = self.agent_card or {}
        interfaces = card.get("supportedInterfaces")
        if isinstance(interfaces, list) and interfaces:
            first = interfaces[0]
            if isinstance(first, dict) and first.get("protocolVersion"):
                return str(first["protocolVersion"])
        return str(card.get("protocolVersion") or self.protocol_version)

    def _message(self, text: str) -> dict[str, Any]:
        """
        Build a message in the shape the target's protocol version expects.

        0.x uses lowercase roles and tags each part with `kind`; 1.x uses the
        enum-style `ROLE_USER` and untagged parts. Sending 1.x shapes to a 0.x
        agent is how a live agent comes back "method not found".
        """
        major = self._card_protocol_version().split(".")[0]
        if major == "1":
            return {
                "messageId": f"msg-{uuid.uuid4()}",
                "role": "ROLE_USER",
                "parts": [{"text": text}],
            }
        return {
            "messageId": f"msg-{uuid.uuid4()}",
            "role": "user",
            "parts": [{"kind": "text", "text": text}],
        }

    def send_message(self, text: str) -> dict[str, Any]:
        interface = self._interface()
        binding = str(
            interface.get("protocolBinding") or interface.get("transport") or "HTTP+JSON"
        ).lower()
        service_url = str(interface["url"]).rstrip("/")
        message = self._message(text)

        if "jsonrpc" in binding:
            major = self._card_protocol_version().split(".")[0]
            method = JSONRPC_METHODS.get(major, JSONRPC_METHODS["0"])
            response = self._request(
                service_url,
                method="POST",
                body={
                    "jsonrpc": "2.0",
                    "id": str(uuid.uuid4()),
                    "method": method,
                    "params": {"message": message},
                },
                content_type="application/json",
                version=self._negotiated_version(),
            )
            if "error" in response:
                raise A2AError(
                    f"A2A error from {service_url} for {method}: {response['error']}"
                )
            return response

        endpoint = f"{service_url}/message:send"
        return self._request(
            endpoint,
            method="POST",
            body={"message": message},
            content_type="application/a2a+json",
            version=self._negotiated_version(),
        )

