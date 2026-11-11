from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .models import ExtractionResult, MessagePayload

DATE_MIN = date(2000, 1, 1)
DATE_MAX = date(2100, 12, 31)
QUOTE_MAX_CHARS = 240
LEGAL_CONCLUSION_PHRASES = frozenset(
    phrase.strip().lower()
    for phrase in (Path(__file__).parent / "data" / "legal_conclusion_phrases.txt").read_text(
        encoding="utf-8"
    ).splitlines()
    if phrase.strip() and not phrase.lstrip().startswith("#")
)


def _normalise_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _normalise_reference(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _check_quoted_field(field_name: str, value: object, quote: str | None, message_text: str) -> None:
    if value is None:
        return
    if not quote:
        raise ValueError(f"{field_name} value requires a source quote")
    if len(quote) > QUOTE_MAX_CHARS:
        raise ValueError(f"{field_name} source quote is over-long")
    if _normalise_text(quote) not in _normalise_text(message_text):
        raise ValueError(f"{field_name} source quote is not present in the message")


def _check_date(field_name: str, value: date | None) -> None:
    if value is not None and not DATE_MIN <= value <= DATE_MAX:
        raise ValueError(f"{field_name} is outside the configured range")


def _check_legal_language(result: ExtractionResult) -> None:
    searchable = [result.evidence_summary, *result.review_reasons]
    lowered = " ".join(searchable).casefold()
    for phrase in LEGAL_CONCLUSION_PHRASES:
        if phrase in lowered:
            raise ValueError(f"legal-conclusion phrase rejected: {phrase}")


def validate_extraction(result: ExtractionResult, message: MessagePayload) -> ExtractionResult:
    """Validate model output against the supplied bounded message and safety rules."""
    if result.message_id != message.message_id:
        raise ValueError("extraction message_id does not match the supplied message")
    message_text = " ".join((message.subject, message.snippet, message.body_text))
    _check_date("event_date", result.event_date.value)
    _check_date("reversal_date", result.reversal_date.value)
    _check_quoted_field(
        "amount", result.amount.value_paise, result.amount.source_quote, message_text
    )
    _check_quoted_field(
        "transaction_reference",
        result.transaction_reference.value,
        result.transaction_reference.source_quote,
        message_text,
    )
    _check_quoted_field("event_date", result.event_date.value, result.event_date.source_quote, message_text)
    _check_quoted_field(
        "reversal_date", result.reversal_date.value, result.reversal_date.source_quote, message_text
    )
    if result.transaction_reference.value is not None and _normalise_reference(
        result.transaction_reference.value
    ) not in _normalise_reference(message_text):
        raise ValueError("transaction reference is not present in the message")
    _check_legal_language(result)
    return result


__all__ = ["DATE_MAX", "DATE_MIN", "LEGAL_CONCLUSION_PHRASES", "validate_extraction"]
