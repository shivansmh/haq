from __future__ import annotations

import re
from dataclasses import dataclass

from .config import LLMSettings, load_settings
from .models import MessagePayload
from .redact import OAuthTokenDetected, RedactionResult, redact_sensitive


@dataclass(frozen=True, slots=True)
class MessageInput:
    """Untrusted pre-provider message fields held only for the current request."""

    message_id: str
    sender: str
    subject: str
    snippet: str
    body_text: str
    received_at: str | None = None


@dataclass(frozen=True, slots=True)
class PreparedPayload:
    """Provider payload plus transient local redaction maps for quote checking."""

    payload: MessagePayload
    redactions: tuple[RedactionResult, ...]

    def restore_quote(self, quote: str) -> str:
        """Restore provider placeholders locally; this object is never provider-serialized."""
        restored = quote
        for redaction in self.redactions:
            restored = redaction.restore(restored)
        return restored


def _normalise_sender(value: str) -> str:
    return " ".join(value.casefold().split())


def _require_opaque_message_id(value: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,200}", value):
        raise ValueError("message_id must be an opaque identifier")


def _bound_fields(subject: str, snippet: str, body_text: str, cap: int) -> tuple[str, str, str]:
    remaining = cap
    bounded_subject = subject[: min(len(subject), 500, remaining)]
    remaining -= len(bounded_subject)
    bounded_snippet = snippet[: min(len(snippet), 2000, remaining)]
    remaining -= len(bounded_snippet)
    bounded_body = body_text[: max(remaining, 0)]
    return bounded_subject, bounded_snippet, bounded_body


def build_provider_payload(
    message: MessageInput,
    settings: LLMSettings | None = None,
) -> PreparedPayload:
    """Redact and bound one message before it can enter a provider adapter."""
    config = settings or load_settings({})
    _require_opaque_message_id(message.message_id)
    fields = (
        redact_sensitive(message.sender),
        redact_sensitive(message.subject),
        redact_sensitive(message.snippet),
        redact_sensitive(message.body_text),
        redact_sensitive(message.received_at or ""),
    )
    sender, subject, snippet, body_text, received_at = fields
    bounded_subject, bounded_snippet, bounded_body = _bound_fields(
        subject.redacted_text,
        snippet.redacted_text,
        body_text.redacted_text,
        config.max_message_chars,
    )
    payload = MessagePayload(
        message_id=message.message_id,
        sender=_normalise_sender(sender.redacted_text),
        subject=bounded_subject,
        snippet=bounded_snippet,
        body_text=bounded_body,
        received_at=received_at.redacted_text or None,
    )
    return PreparedPayload(payload, fields)


__all__ = [
    "MessageInput",
    "PreparedPayload",
    "build_provider_payload",
    "OAuthTokenDetected",
]
