from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any


class A2AError(RuntimeError):
    """Raised when an A2A endpoint cannot complete an operation."""


USER_AGENT = "project-beacon/0.1"

JSONRPC_METHODS = {
    # A2A 0.x, which is what deployed agents actually speak.
    "0": "message/send",
    # A2A 1.x renamed the JSON-RPC methods.
    "1": "SendMessage",
}


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
    ) -> None:
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("A2A base URL must use http or https")
        self.base_url = base_url.rstrip("/")
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

    def _request(
        self,
        url: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        content_type: str = "application/json",
    ) -> dict[str, Any]:
        headers = {
            "Accept": "application/a2a+json, application/json",
            "A2A-Version": self.protocol_version,
            # Agents behind a WAF reject the default Python-urllib agent with
            # a 403, which reads as "the agent refused" rather than "we were
            # filtered". Identify ourselves.
            "User-Agent": USER_AGENT,
        }
        data = None
        if body is not None:
            data = json.dumps(body, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = content_type
        if self.authorization:
            headers["Authorization"] = self.authorization
        request = urllib.request.Request(
            url,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
                context=_ssl_context(),
            ) as response:
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
                "transport": card.get("preferredTransport", "HTTP+JSON"),
                "protocolVersion": self._card_protocol_version(),
            }

        additional = card.get("additionalInterfaces")
        if isinstance(additional, list) and additional:
            interface = additional[0]
            if isinstance(interface, dict) and interface.get("url"):
                return interface

        raise A2AError("Agent Card does not declare a supported interface URL")

    def _card_protocol_version(self) -> str:
        card = self.agent_card or {}
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
        )

