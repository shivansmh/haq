from __future__ import annotations

from datetime import date
from email.utils import parsedate_to_datetime
from hashlib import sha256
from typing import Any

from api.upi_signals import Signal, classify_message
from clean.redact import redact_sensitive

from .models import Event, EventType

_KIND_TO_EVENT: dict[str, EventType] = {
    "debit": "debit",
    "upi_failed": "payment_failed",
    "upi_failed_debited": "payment_failed",
    "refund_credited": "refund_credited",
    "invoice_paid": "payment_received",
    "order_cancelled": "order_cancelled",
    "atm_failure": "atm_cash_not_dispensed",
    "overdue_invoice": "invoice_overdue",
}


def _date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).date()
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def _claim_type(signal: Signal) -> str:
    if signal.kind == "atm_failure":
        return "atm_cash_not_dispensed"
    if signal.kind in {"overdue_invoice", "invoice_paid"}:
        return "msme_invoice_overdue"
    if signal.kind == "order_cancelled":
        return "order_cancelled_refund_delayed"
    if signal.channel == "CARD":
        return "card_debited_order_unconfirmed"
    return "upi_failed_debited"


def normalize_email(message: dict[str, Any], signal: Signal | None = None) -> Event | None:
    """Normalize one message. Pass the already-computed signal to avoid parsing twice."""
    sender = str(message.get("sender", ""))
    subject = str(message.get("subject", ""))
    snippet = str(message.get("snippet", ""))
    body = str(message.get("body", ""))
    signal = signal or classify_message(sender, subject, snippet, body)
    event_type = _KIND_TO_EVENT.get(signal.kind)
    if event_type is None:
        return None
    email_id = str(message.get("id") or message.get("message_id") or "unknown")
    quote = body.strip() or snippet.strip() or subject.strip()
    event_id = sha256(f"{email_id}:{event_type}:{signal.ref}:{signal.amount_paise}".encode()).hexdigest()[:16]
    return Event(
        event_id=event_id,
        email_id=email_id,
        claim_type=_claim_type(signal),
        event_type=event_type,
        amount_paise=signal.amount_paise,
        reference=signal.ref,
        event_date=_date(message.get("date")),
        quote=redact_sensitive(quote[:2000]),
        sender=sender,
        subject=subject,
        confidence="High" if signal.sender_tier in {"bank", "upi_app", "merchant"} else "Medium",
        reasons=list(signal.reasons),
        signal_kind=signal.kind,
        channel=signal.channel,
    )


def normalize_emails(
    messages: list[dict[str, Any]],
    signals_by_id: dict[str, Signal] | None = None,
) -> list[Event]:
    """Normalize messages, reusing signals from the sweep's first classification pass."""
    return [
        event
        for message in messages
        if (
            event := normalize_email(
                message,
                (signals_by_id or {}).get(str(message.get("id", ""))),
            )
        )
        is not None
    ]
