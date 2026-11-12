"""Optional Groq labelling for flagged records.

The model is a *labeller*, not a judge. Its output is merged only into the
`ai` block; deterministic amount, rule, compliance, status and evidence always
stay authoritative. Any disagreement becomes a visible conflict flag.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

from .client import LLMClient, LLMResponse
from .config import LLMSettings
from .models import LedgerResult, LLMStatus
from .payload import MessageInput, build_provider_payload
from .redact import OAuthTokenDetected
from .redact import redact_sensitive as redact_provider_text

_LEDGER_CACHE: dict[str, tuple[float, LLMResponse[LedgerResult]]] = {}
_LEDGER_CACHE_TTL = 1800.0
_LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9:_.-]{0,47}$")


def _safe_text(value: str) -> str:
    try:
        return redact_provider_text(str(value or "")).redacted_text[:400]
    except OAuthTokenDetected:
        return "[CREDENTIAL REDACTED]"


def _compact_record(record: Any) -> str:
    """Small, redaction-friendly view; never includes tracking timestamps or AI output."""
    payload = {
        "record_id": record.record_id,
        "claim_type": record.claim_type,
        "title": record.title,
        "category_label": record.category_label,
        "amount": record.amount.display,
        "channel": record.transaction.channel,
        "reference": record.transaction.reference,
        "merchant": record.transaction.merchant,
        "segment": record.segment,
        "vertical": record.vertical,
        "resolution": record.resolution.label,
        "rule_status": record.legal.rule_status,
        "labels": record.labels,
        "evidence": [
            {
                "role": item.role,
                "subject": item.subject,
                "quote": item.quote,
            }
            for item in record.evidence[:6]
        ],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _cache_key(payload_json: str) -> str:
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def _cached_ledger(client: LLMClient, payload: Any, cache_text: str) -> LLMResponse[LedgerResult]:
    key = _cache_key(cache_text)
    now = time.monotonic()
    cached = _LEDGER_CACHE.get(key)
    if cached and now - cached[0] < _LEDGER_CACHE_TTL:
        return cached[1]
    response = client.ledger(payload)
    _LEDGER_CACHE[key] = (now, response)
    if len(_LEDGER_CACHE) > 2048:
        oldest = min(_LEDGER_CACHE, key=lambda item: _LEDGER_CACHE[item][0])
        _LEDGER_CACHE.pop(oldest, None)
    return response


def _merge(record: Any, result: LedgerResult) -> Any:
    conflicts: list[str] = []
    if result.merchant and record.transaction.merchant:
        if result.merchant.strip().casefold() != record.transaction.merchant.strip().casefold():
            conflicts.append("merchant")
    if record.vertical != "other" and result.vertical.value != record.vertical:
        conflicts.append("vertical")
    if result.segment.value != record.segment:
        conflicts.append("segment")

    labels = list(record.labels)
    for label in result.labels:
        cleaned = label.strip().casefold()
        if _LABEL_RE.match(cleaned) and cleaned not in labels:
            labels.append(cleaned)

    risk_flags = list(record.risk_flags)
    if conflicts and "ai_conflict" not in risk_flags:
        risk_flags.append("ai_conflict")

    ai = record.ai.model_copy(
        update={
            "status": LLMStatus.OK.value,
            "model": result.model_version,
            "summary": _safe_text(result.summary),
            "merchant": _safe_text(result.merchant) if result.merchant else None,
            "vertical": result.vertical.value,
            "segment": result.segment.value,
            "labels": result.labels[:8],
            "conflicts": conflicts,
            "needs_review": bool(result.needs_review or conflicts),
        }
    )
    return record.model_copy(
        update={
            "ai": ai,
            "labels": labels[:24],
            "risk_flags": risk_flags,
            "needs_review": bool(record.needs_review or result.needs_review or conflicts),
        }
    )


def enrich_flagged_records(
    records: list[Any],
    *,
    client: LLMClient | None,
    settings: LLMSettings,
) -> tuple[list[Any], str]:
    """Add advisory labels to up to `max_records_per_sweep` records; fail open."""
    if client is None:
        return records, LLMStatus.DISABLED.value
    enriched: list[Any] = []
    statuses: list[str] = []
    sent = 0
    for record in records:
        if sent >= settings.max_records_per_sweep or not record.evidence:
            enriched.append(record)
            continue
        compact = _compact_record(record)
        try:
            prepared = build_provider_payload(
                MessageInput(
                    message_id=record.record_id,
                    sender="haq-ledger",
                    subject=record.title,
                    snippet=record.category_label,
                    body_text=compact,
                ),
                settings,
            )
        except (OAuthTokenDetected, ValueError, TypeError):
            enriched.append(
                record.model_copy(update={"ai": record.ai.model_copy(update={"status": LLMStatus.INVALID_OUTPUT.value, "needs_review": True})})
            )
            statuses.append(LLMStatus.INVALID_OUTPUT.value)
            sent += 1
            continue
        sent += 1
        response = _cached_ledger(client, prepared.payload, prepared.payload.model_dump_json())
        if response.llm_status != LLMStatus.OK or response.result is None:
            statuses.append(response.llm_status.value)
            enriched.append(
                record.model_copy(
                    update={
                        "ai": record.ai.model_copy(
                            update={"status": response.llm_status.value, "needs_review": True}
                        )
                    }
                )
            )
            continue
        if response.result.record_id != record.record_id:
            statuses.append(LLMStatus.INVALID_OUTPUT.value)
            enriched.append(
                record.model_copy(
                    update={
                        "ai": record.ai.model_copy(
                            update={"status": LLMStatus.INVALID_OUTPUT.value, "needs_review": True}
                        )
                    }
                )
            )
            continue
        statuses.append(LLMStatus.OK.value)
        enriched.append(_merge(record, response.result))

    summary = (
        next((status for status in statuses if status != LLMStatus.OK.value), LLMStatus.OK.value)
        if statuses
        else LLMStatus.OK.value
    )
    return enriched, summary


__all__ = ["enrich_flagged_records"]
