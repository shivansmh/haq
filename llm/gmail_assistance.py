from __future__ import annotations

import re
from datetime import date
from typing import Any

from .client import LLMClient
from .config import LLMSettings
from .models import FieldStatus, LLMStatus
from .payload import MessageInput, build_provider_payload
from .redact import OAuthTokenDetected, redact_sensitive
from .trust import FieldTrustTier, assign_tier, report_conflicts
from .verify import AmbiguousDateError, normalise_date, verify_quote

_NUMERIC_DATE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
_TEXTUAL_DATE = re.compile(r"\b\d{1,2}[ -](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[ ,-]+\d{4}\b", re.I)
_ISO_DATE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")


def _safe_text(value: str) -> str:
    """Apply the A2 redactor before any provider-derived free text is returned."""
    return redact_sensitive(value).redacted_text[:500]


def _verify_date_quote(value: date, quote: str, original: str) -> None:
    for match in _NUMERIC_DATE.finditer(quote):
        try:
            normalise_date(match.group(0))
        except AmbiguousDateError:
            raise
        except ValueError:
            continue
    if not (_NUMERIC_DATE.search(quote) or _TEXTUAL_DATE.search(quote) or _ISO_DATE.search(quote)):
        # A3 quote verification still checks the original source and normalized value.
        verify_quote(original, quote, value, kind="date")
        return
    verify_quote(original, quote, value, kind="date")


def _verify_fields(result: Any, payload_json: str) -> tuple[dict[str, Any], list[str]]:
    suggestions: dict[str, Any] = {}
    reasons: list[str] = []
    fields = (
        ("amount_paise", result.amount, "amount"),
        ("transaction_reference", result.transaction_reference, "reference"),
        ("event_date", result.event_date, "date"),
        ("reversal_date", result.reversal_date, "date"),
    )
    for name, field, kind in fields:
        value = field.value_paise if name == "amount_paise" else field.value
        if field.status != FieldStatus.PRESENT or value is None:
            if field.status == FieldStatus.AMBIGUOUS:
                reasons.append(f"{name}_ambiguous")
            continue
        try:
            if kind == "date":
                _verify_date_quote(value, field.source_quote or "", payload_json)
            else:
                verify_quote(payload_json, field.source_quote or "", value, kind=kind)
            tier = assign_tier(source="ai", verified_in_text=True)
            if tier != FieldTrustTier.T_B:
                raise ValueError("unexpected trust tier")
            suggestions[name] = {
                "value": value.isoformat() if isinstance(value, date) else value,
                "source_quote": field.source_quote,
                "trust_tier": tier.value,
            }
        except (ValueError, TypeError):
            reasons.append(f"{name}_quote_unverified")
    return suggestions, reasons


def _deterministic_values(email: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {
        "amount_paise": email.get("extractedAmount"),
        "transaction_reference": email.get("extractedRef"),
    }
    raw_date = email.get("date")
    if raw_date:
        try:
            from api.gmail_service import parse_message_date

            parsed = parse_message_date(str(raw_date))
            values["event_date"] = date.fromisoformat(parsed) if parsed else None
        except (ValueError, TypeError):
            values["event_date"] = None
    return {key: value for key, value in values.items() if value is not None}


def enrich_financial_emails(
    raw_messages: list[dict[str, Any]],
    emails: list[dict[str, Any]],
    *,
    client: LLMClient | None,
    settings: LLMSettings,
) -> tuple[list[dict[str, Any]], str]:
    """Attach advisory, quote-verified suggestions to prefiltered financial messages.

    Calls are sequential and strictly per message. Returned suggestions never alter
    the deterministic emails, candidates, or calculator inputs.
    """
    if client is None:
        return emails, LLMStatus.DISABLED.value

    by_id = {str(message.get("id", "")): message for message in raw_messages}
    enriched: list[dict[str, Any]] = []
    statuses: list[str] = []
    sent = 0
    for email in emails:
        entry = dict(email)
        if entry.get("status") == "noise" or sent >= settings.max_messages_per_sweep:
            enriched.append(entry)
            continue
        raw = by_id.get(str(entry.get("id", "")))
        if not raw:
            enriched.append(entry)
            continue
        try:
            prepared = build_provider_payload(
                MessageInput(
                    message_id=str(raw.get("id", "")),
                    sender=str(raw.get("sender", "")),
                    subject=str(raw.get("subject", "")),
                    snippet=str(raw.get("snippet", "")),
                    body_text=str(raw.get("body", "")),
                    received_at=str(raw.get("date", "")) or None,
                ),
                settings,
            )
        except (OAuthTokenDetected, ValueError, TypeError):
            status = LLMStatus.INVALID_OUTPUT.value
            statuses.append(status)
            entry["llm_assistance"] = {"status": status, "needs_review": True}
            enriched.append(entry)
            sent += 1
            continue
        sent += 1
        response = client.extract(prepared.payload)
        status = response.llm_status.value
        statuses.append(status)
        if status != LLMStatus.OK.value or response.result is None:
            entry["llm_assistance"] = {"status": status, "needs_review": True}
            enriched.append(entry)
            continue
        result = response.result
        try:
            original = prepared.payload.model_dump_json()
            suggestions, verification_reasons = _verify_fields(result, original)
            conflicts = report_conflicts(_deterministic_values(entry), {
                key: value["value"] for key, value in suggestions.items()
            })
            reasons = [*_safe_reasons(result.review_reasons), *verification_reasons]
            if conflicts:
                reasons.append("deterministic_model_conflict")
            entry["llm_assistance"] = {
                "status": status,
                "relevance": result.relevance.value,
                "signal_type": result.signal_type.value,
                "evidence_summary": _safe_text(result.evidence_summary),
                "needs_review": bool(result.needs_review or verification_reasons or conflicts),
                "review_reasons": reasons[:10],
                "suggestions": suggestions,
                "conflicts": conflicts,
                "trust_tier": FieldTrustTier.T_B.value,
            }
        except Exception:
            # Fail closed: malformed provider output never makes a sweep fail.
            entry["llm_assistance"] = {"status": LLMStatus.INVALID_OUTPUT.value, "needs_review": True}
            statuses[-1] = LLMStatus.INVALID_OUTPUT.value
        enriched.append(entry)
    summary = next((status for status in statuses if status != LLMStatus.OK.value), LLMStatus.OK.value) if statuses else LLMStatus.OK.value
    return enriched, summary


def _safe_reasons(reasons: list[str]) -> list[str]:
    safe: list[str] = []
    for reason in reasons[:10]:
        try:
            safe.append(_safe_text(str(reason)))
        except OAuthTokenDetected:
            safe.append("provider_review_required")
    return safe


__all__ = ["enrich_financial_emails"]
