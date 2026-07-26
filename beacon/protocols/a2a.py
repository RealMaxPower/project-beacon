from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any


class A2AError(RuntimeError):
    """Raised when an A2A endpoint cannot complete an operation."""


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

    @property
    def card_url(self) -> str:
        if self.base_url.endswith("agent-card.json"):
            return self.base_url
        return f"{self.base_url}/.well-known/agent-card.json"

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
        card = self._request(self.card_url)
        self.agent_card = card
        return card

    def _interface(self) -> dict[str, Any]:
        card = self.agent_card or self.discover()
        interfaces = card.get("supportedInterfaces", [])
        if isinstance(interfaces, list) and interfaces:
            interface = interfaces[0]
            if isinstance(interface, dict) and interface.get("url"):
                return interface
        if card.get("url"):
            return {
                "url": card["url"],
                "protocolBinding": "HTTP+JSON",
                "protocolVersion": self.protocol_version,
            }
        raise A2AError("Agent Card does not declare a supported interface URL")

    def send_message(self, text: str) -> dict[str, Any]:
        interface = self._interface()
        binding = str(interface.get("protocolBinding", "HTTP+JSON")).lower()
        service_url = str(interface["url"]).rstrip("/")
        message = {
            "messageId": f"msg-{uuid.uuid4()}",
            "role": "ROLE_USER",
            "parts": [{"text": text}],
        }

        if "jsonrpc" in binding:
            return self._request(
                service_url,
                method="POST",
                body={
                    "jsonrpc": "2.0",
                    "id": str(uuid.uuid4()),
                    "method": "SendMessage",
                    "params": {"message": message},
                },
                content_type="application/json",
            )

        endpoint = f"{service_url}/message:send"
        return self._request(
            endpoint,
            method="POST",
            body={"message": message},
            content_type="application/a2a+json",
        )

