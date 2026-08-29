from __future__ import annotations

import base64
import json
import re
import urllib.parse
from typing import Any


class SecretError(ValueError):
    """Raised when a secret cannot be handled safely."""


MINIMUM_SECRET_LENGTH = 8

SECRET_LOOKING_NAME = re.compile(
    r"(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH|SESSION|COOKIE|PRIVATE)",
    re.IGNORECASE,
)
"""
Names that almost certainly carry a credential.

Passing one through without marking it secret is the mistake worth catching at
the CLI: it leaves the value free to reach the evidence bundle, which is the
artifact people share.
"""

REDACTION_NOTICE = (
    "Secret values were removed from this evidence bundle by exact match. A "
    "subject that transforms a secret before emitting it - splitting, "
    "re-encoding, or paraphrasing it - defeats that, and the subject's network "
    "access is not restricted."
)


def looks_like_a_secret(name: str) -> bool:
    return bool(SECRET_LOOKING_NAME.search(name))


class SecretRegistry:
    """
    Removes known secret values from anything on its way into evidence.

    Pattern-matching arbitrary credentials is unreliable, but redacting the
    exact values Beacon itself injected is not: those values are known. Common
    re-encodings are registered alongside the raw value, because a subject that
    puts a key in a URL or an Authorization header emits it transformed.

    This is a containment measure, not a guarantee. `REDACTION_NOTICE` states
    the limit, and belongs in the evidence bundle whenever this is in use.
    """

    def __init__(self) -> None:
        self._replacements: dict[str, str] = {}
        self._names: list[str] = []
        self._hits = 0

    @property
    def active(self) -> bool:
        return bool(self._replacements)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._names)

    @property
    def redaction_count(self) -> int:
        return self._hits

    def register(self, name: str, value: str) -> None:
        if not value:
            raise SecretError(f"{name} is empty, so there is nothing to pass through")
        if len(value) < MINIMUM_SECRET_LENGTH:
            raise SecretError(
                f"{name} is shorter than {MINIMUM_SECRET_LENGTH} characters. "
                f"Redacting a short value would corrupt unrelated text that "
                f"happens to contain it."
            )
        placeholder = f"[redacted:{name}]"
        for variant in self._variants(value):
            self._replacements.setdefault(variant, placeholder)
        if name not in self._names:
            self._names.append(name)

    @staticmethod
    def _variants(value: str) -> list[str]:
        """
        The raw value plus the encodings it is likely to be wearing.

        The JSON-escaped form is here because *Beacon* puts it there.
        `MCPToolSubjectAdapter._flatten` serialises a tool's `structuredContent`
        with `json.dumps` and stores the result as the graded artifact, so a
        credential containing a quote, a backslash or a newline reaches
        `evidence.json` already escaped — and this registry matched raw
        substrings, so it never found it. The bundle then published
        `replacements: 0`, which is not silence but a positive claim that the
        scan ran and found nothing.

        `REDACTION_NOTICE` does not cover that. It disclaims a *subject* that
        transforms a secret before emitting it; here the transforming is ours.

        Both `ensure_ascii` settings are registered: Beacon writes with it off,
        and a subject echoing the value through a default `json.dumps` writes
        with it on.
        """
        variants = [value]
        encoded = urllib.parse.quote(value, safe="")
        if encoded != value:
            variants.append(encoded)
        for ascii_only in (False, True):
            # `[1:-1]` strips the quotes `dumps` adds, leaving the escaped body
            # exactly as it appears inside a serialised string.
            escaped = json.dumps(value, ensure_ascii=ascii_only)[1:-1]
            if escaped != value and escaped not in variants:
                variants.append(escaped)
        try:
            variants.append(base64.b64encode(value.encode("utf-8")).decode("ascii"))
        except (UnicodeError, ValueError):  # pragma: no cover - defensive
            pass
        return variants

    def redact_text(self, text: str) -> str:
        for value, placeholder in self._replacements.items():
            if value in text:
                self._hits += text.count(value)
                text = text.replace(value, placeholder)
        return text

    def redact(self, value: Any) -> Any:
        """Walk a JSON-shaped structure, redacting strings and dictionary keys."""
        if not self._replacements:
            return value
        if isinstance(value, str):
            return self.redact_text(value)
        if isinstance(value, dict):
            return {
                self.redact(key) if isinstance(key, str) else key: self.redact(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self.redact(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self.redact(item) for item in value)
        return value
