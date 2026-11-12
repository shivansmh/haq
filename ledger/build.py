from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from hashlib import sha256

from cases.models import Case
from engine.models import RightEntry
from engine.registry_loader import Registry, load_registry
from events.models import Event
from llm.redact import OAuthTokenDetected
from llm.redact import redact_sensitive as redact_provider_text
from taxonomy.loader import load_taxonomy
from taxonomy.models import TaxonomyCatalog

from .labels import (
    detect_merchant,
    detect_segment,
    detect_vertical,
    labels_for,
    recommended_actions,
)
from .models import (
    AIEnrichment,
    Compensation,
    EmailFlag,
    EvidenceEmail,
    EvidenceRole,
    FlaggedRecord,
    LegalAssessment,
    Money,
    Resolution,
    TimelineItem,
    Tracking,
    TransactionInfo,
)

RESOLUTION_EVENTS = {"refund_credited", "payment_received"}

_ROLE: dict[str, EvidenceRole] = {
    "debit": "debit",
    "payment_failed": "failure",
    "refund_credited": "refund",
    "payment_received": "payment",
    "order_cancelled": "cancellation",
    "atm_cash_not_dispensed": "atm_failure",
    "invoice_overdue": "invoice",
}

_EVENT_LABEL = {
    "debit": "Money debited",
    "payment_failed": "Payment failed",
    "refund_credited": "Refund credited",
    "payment_received": "Invoice payment received",
    "order_cancelled": "Order cancelled",
    "atm_cash_not_dispensed": "ATM cash not dispensed",
    "invoice_overdue": "Invoice marked overdue",
}

_CATEGORY_LABEL = {
    "upi_failed_debited": "Failed payment, money debited",
    "card_debited_order_unconfirmed": "Card payment without order confirmation",
    "order_cancelled_refund_delayed": "Cancelled order / delayed refund",
    "atm_cash_not_dispensed": "ATM cash not dispensed",
    "msme_invoice_overdue": "Overdue business invoice",
}

_CITATION = {
    "R-001": "RBI Harmonised TAT circular (DPSS.CO.PD No.629/02.01.014/2019-20)",
    "R-002": "RBI Harmonised TAT circular (DPSS.CO.PD No.629/02.01.014/2019-20)",
    "R-003": "RBI Harmonised TAT circular (DPSS.CO.PD No.629/02.01.014/2019-20)",
    "R-004": "RBI Harmonised TAT circular (DPSS.CO.PD No.629/02.01.014/2019-20)",
    "R-005": "RBI Harmonised TAT circular (DPSS.CO.PD No.629/02.01.014/2019-20)",
    "R-006": "RBI Harmonised TAT circular (DPSS.CO.PD No.629/02.01.014/2019-20)",
    "R-007": "MSMED Act 2006 (Sections 15-16)",
    "R-008": "MSMED Act 2006 (Section 16 interest)",
}

_RESOLUTION_NOUN = {"payment": "Payment", "cash": "Cash reversal", "refund": "Refund"}


def _compliance_label(compliance: str, noun: str) -> str:
    lower = noun.lower()
    return {
        "on_time": f"{noun} received within the rule's turnaround time",
        "late": f"{noun} received after the rule's turnaround time",
        "received_rule_unverified": f"{noun} received; the linked rule is not verified",
        "not_due_yet": "Still within the rule's turnaround time",
        "not_received_past_deadline": f"No {lower} after the rule's turnaround time",
        "not_received_rule_unverified": f"No {lower} yet; the linked rule is not verified",
        "unknown": "Not enough information to compare with a rule",
    }[compliance]


def _safe(value: object) -> str:
    try:
        return redact_provider_text(str(value or "")).redacted_text[:2000]
    except OAuthTokenDetected:
        return "[CREDENTIAL REDACTED]"


def _money(amount_paise: int | None) -> Money:
    if amount_paise is None:
        return Money(value_paise=None, display="Amount not found")
    return Money(value_paise=amount_paise, display=f"₹{amount_paise / 100:,.2f}")


def _resolution_kind(claim_type: str) -> str:
    if claim_type == "msme_invoice_overdue":
        return "payment"
    if claim_type == "atm_cash_not_dispensed":
        return "cash"
    return "refund"


def _resolution_label(kind: str, received: bool) -> str:
    noun = {"payment": "Payment", "cash": "Cash reversal", "refund": "Refund", "reversal": "Reversal"}.get(kind, "Refund")
    return f"{noun} received" if received else f"{noun} not seen yet"


def _entry_for(rule_id: str | None, registry: Registry) -> RightEntry | None:
    if not rule_id:
        return None
    try:
        return registry.get(rule_id)
    except ValueError:
        return None


def _legal(
    *,
    claim_type: str,
    rule_id: str | None,
    rule_status: str,
    entry: RightEntry | None,
    origin_date: date | None,
    resolved_on: date | None,
    today: date,
    kind: str,
) -> LegalAssessment:
    offset = entry.clock.offset if entry else None
    daily_rate = None
    if entry and isinstance(entry.amount.parameters.get("daily_rate_paise"), int):
        daily_rate = int(entry.amount.parameters["daily_rate_paise"])
    verified = bool(entry and entry.status == "Verified" and offset is not None)
    deadline = origin_date + timedelta(days=offset) if origin_date and verified and offset is not None else None
    indicative = (
        origin_date + timedelta(days=offset)
        if origin_date and not verified and offset is not None
        else None
    )
    resolution_received = resolved_on is not None

    if verified and deadline is not None:
        if resolution_received:
            compliance = "on_time" if resolved_on <= deadline else "late"
            days_overdue = max(0, (resolved_on - deadline).days)
        elif today > deadline:
            compliance = "not_received_past_deadline"
            days_overdue = max(0, (today - deadline).days)
        else:
            compliance = "not_due_yet"
            days_overdue = 0
    elif resolution_received:
        compliance = "received_rule_unverified"
        days_overdue = None
    elif entry is not None:
        compliance = "not_received_rule_unverified"
        days_overdue = None
    else:
        compliance = "unknown"
        days_overdue = None

    computed = False
    amount_paise = None
    indicative_paise = None
    if verified and deadline is not None and daily_rate is not None:
        computed = True
        if resolution_received:
            amount_paise = max(0, (resolved_on - deadline).days) * daily_rate
        else:
            amount_paise = max(0, (today - deadline).days) * daily_rate
    elif indicative is not None and daily_rate is not None:
        anchor = resolved_on or today
        indicative_paise = max(0, (anchor - indicative).days) * daily_rate

    if computed:
        compensation_note = (
            f"Computed at ₹{daily_rate / 100:,.2f}/day beyond the verified deadline."
            if amount_paise
            else "No compensation is due on the dates currently recorded."
        )
    elif indicative is not None:
        compensation_note = (
            "Indicative only: the linked rule is not verified, so Haq does not treat this as a legal amount."
        )
    else:
        compensation_note = "No verified daily-rate rule is linked, so no compensation is computed."

    if verified:
        stamp = "VERIFIED RULE"
        note = f"The linked rule {rule_id} is Verified in the registry."
    elif entry is not None:
        stamp = "UNVERIFIED RULE"
        note = (
            f"The linked rule {rule_id} is {rule_status}, so the turnaround time and any amount are "
            "shown only as an indicative reference, not a legal conclusion."
        )
    else:
        stamp = "NO RULE"
        note = "No verified registry rule is linked yet; this record is evidence-first."

    return LegalAssessment(
        rule_id=rule_id,
        rule_status=rule_status,
        rule_verified=verified,
        stamp=stamp,
        statutory_days=offset,
        deadline_date=deadline,
        indicative_deadline_date=indicative,
        days_overdue=days_overdue,
        compliance=compliance,  # type: ignore[arg-type]
        compliance_label=_compliance_label(compliance, _RESOLUTION_NOUN.get(kind, "Refund")),
        compensation=Compensation(
            computed=computed,
            amount_paise=amount_paise,
            indicative_paise=indicative_paise,
            daily_rate_paise=daily_rate,
            note=compensation_note,
        ),
        citation=_CITATION.get(rule_id or "") or (entry.sources[0].instrument if entry and entry.sources else None),
        note=note,
    )


def _status(
    *,
    resolution_received: bool,
    compliance: str,
    has_rule: bool,
    kind: str,
) -> tuple[str, str]:
    noun = _RESOLUTION_NOUN.get(kind, "Refund")
    lower = noun.lower()
    if resolution_received:
        if compliance == "late":
            return "action_needed", f"{noun} was late; check compensation"
        return "resolved", f"{noun} received"
    if compliance == "not_received_past_deadline":
        return "action_needed", f"Past deadline, no {lower}"
    if compliance in {"not_received_rule_unverified", "not_due_yet"}:
        return "tracking", f"Waiting for {lower}"
    if not has_rule:
        return "reference_only", "Evidence saved"
    return "tracking", "Tracking"


def _record_id(
    claim_type: str,
    reference: str | None,
    amount_paise: int | None,
    merchant: str | None,
    origin_date: date | None,
) -> str:
    key = "|".join(
        [
            claim_type,
            reference or "",
            str(amount_paise or ""),
            (merchant or "").casefold(),
            origin_date.isoformat() if origin_date else "",
        ]
    )
    return "hf_" + sha256(key.encode("utf-8")).hexdigest()[:16]


def _identity_keys(
    *,
    claim_type: str,
    reference: str | None,
) -> list[str]:
    """Hints for cross-sweep matching, strongest first.

    Only a claim-scoped transaction reference is strong enough for an exact
    cross-sweep join. Amount and merchant are deliberately not global identity
    keys: repeat purchases can have the same value and counterparty.
    """
    keys: list[str] = []
    if reference:
        keys.append(f"claim:{claim_type}|ref:{reference.strip().casefold()}")
    return list(dict.fromkeys(keys))


def _evidence(events: list[Event]) -> list[EvidenceEmail]:
    rows: list[EvidenceEmail] = []
    seen: dict[tuple[object, ...], str] = {}
    for event in events:
        role = _ROLE.get(event.event_type, "other")
        key = (
            role,
            event.amount_paise,
            event.reference,
            event.event_date,
            event.subject.casefold().strip(),
        )
        duplicate_of = seen.get(key)
        row = EvidenceEmail(
            email_id=event.email_id,
            role=role,
            duplicate=duplicate_of is not None,
            duplicate_of=duplicate_of,
            date=event.event_date,
            sender=_safe(event.sender),
            subject=_safe(event.subject),
            quote=_safe(event.quote),
            amount_paise=event.amount_paise,
            reference=event.reference,
        )
        rows.append(row)
        if duplicate_of is None:
            seen[key] = event.email_id
    return rows


def build_flagged_records(
    cases: list[Case],
    *,
    today: date | None = None,
    taxonomy: TaxonomyCatalog | None = None,
    registry: Registry | None = None,
    now: datetime | None = None,
) -> list[FlaggedRecord]:
    """Turn grouped cases into stable, structured records with refund tracking."""
    taxonomy = taxonomy or load_taxonomy()
    registry = registry or load_registry()
    effective_today = today or date.today()
    seen_at = now or datetime.now(timezone.utc)
    records: list[FlaggedRecord] = []

    for case in cases:
        spec = taxonomy.get(case.claim_type)
        events = sorted(case.events, key=lambda event: (event.event_date or date.min, event.event_id))
        origins = [event for event in events if event.event_type not in RESOLUTION_EVENTS]
        resolutions = [event for event in events if event.event_type in RESOLUTION_EVENTS]
        origin_date = min((event.event_date for event in origins if event.event_date), default=None)
        resolved_on = max((event.event_date for event in resolutions if event.event_date), default=None)
        if origin_date is None:
            origin_date = min((event.event_date for event in events if event.event_date), default=None)

        merchant = detect_merchant(
            origins[0].sender if origins else (events[0].sender if events else ""),
            *(f"{event.subject} {event.quote}" for event in origins),
        )
        haystack = " ".join(f"{event.subject} {event.quote}" for event in events)
        vertical = detect_vertical(case.claim_type, merchant, haystack)
        segment = detect_segment(case.claim_type, vertical, haystack)
        kind = _resolution_kind(case.claim_type)
        resolution_received = resolved_on is not None
        entry = _entry_for(case.rule_id, registry)
        legal = _legal(
            claim_type=case.claim_type,
            rule_id=case.rule_id,
            rule_status=case.rule_status,
            entry=entry,
            origin_date=origin_date,
            resolved_on=resolved_on,
            today=effective_today,
            kind=kind,
        )
        status, status_label = _status(
            resolution_received=resolution_received,
            compliance=legal.compliance,
            has_rule=case.rule_id is not None,
            kind=kind,
        )
        evidence = _evidence(events)
        amount_paise = case.amount_paise
        risk_flags: list[str] = []
        if not legal.rule_verified:
            risk_flags.append("rule_not_verified")
        if not resolution_received:
            risk_flags.append("payment_not_received" if kind == "payment" else "refund_not_received")
        if legal.compliance == "late":
            risk_flags.append("refund_late")
        if amount_paise is None:
            risk_flags.append("amount_missing")
        if not case.reference:
            risk_flags.append("reference_missing")
        if any(row.duplicate for row in evidence):
            risk_flags.append("duplicate_emails")

        timeline = [
            TimelineItem(
                date=event.event_date,
                event=_EVENT_LABEL.get(event.event_type, event.event_type.replace("_", " ")),
                email_id=event.email_id,
                amount_paise=event.amount_paise,
            )
            for event in events
        ]
        signal_kinds = {event.signal_kind for event in events if event.signal_kind}
        channel = next((event.channel for event in events if event.channel), "")
        labels = labels_for(
            claim_type=case.claim_type,
            channel=channel,
            merchant=merchant,
            vertical=vertical,
            segment=segment,
            resolution_received=resolution_received,
            rule_status=case.rule_status,
            signal_kinds=signal_kinds,
        )

        records.append(
            FlaggedRecord(
                record_id=_record_id(case.claim_type, case.reference, amount_paise, merchant, origin_date),
                identity_keys=_identity_keys(
                    claim_type=case.claim_type,
                    reference=case.reference,
                ),
                case_id=case.case_id,
                title=spec.name,
                claim_type=case.claim_type,
                category_label=_CATEGORY_LABEL.get(case.claim_type, spec.name),
                segment=segment,
                vertical=vertical,
                status=status,  # type: ignore[arg-type]
                status_label=status_label,
                amount=_money(amount_paise),
                transaction=TransactionInfo(
                    reference=case.reference,
                    channel=channel,
                    merchant=merchant,
                    origin_date=origin_date,
                    origin_email_id=origins[0].email_id if origins else None,
                ),
                resolution=Resolution(
                    kind=kind,  # type: ignore[arg-type]
                    received=resolution_received,
                    received_on=resolved_on,
                    days_to_resolution=(resolved_on - origin_date).days
                    if resolved_on and origin_date and resolved_on >= origin_date
                    else None,
                    evidence_email_ids=[event.email_id for event in resolutions],
                    label=_resolution_label(kind, resolution_received),
                ),
                legal=legal,
                labels=labels,
                risk_flags=risk_flags,
                evidence=evidence,
                timeline=timeline,
                recommended_actions=recommended_actions(
                    claim_type=case.claim_type,
                    status=status,
                    resolution_received=resolution_received,
                    compliance=legal.compliance,
                    segment=segment,
                ),
                ai=AIEnrichment(),
                tracking=Tracking(first_seen_at=seen_at, last_seen_at=seen_at),
                needs_review=amount_paise is None or any(row.duplicate for row in evidence),
            )
        )
    return records


def project_email(record: FlaggedRecord, email_id: str) -> EmailFlag | None:
    """Return the compact per-email JSON for one piece of evidence."""
    row = next((item for item in record.evidence if item.email_id == email_id), None)
    if row is None:
        return None
    labels = list(dict.fromkeys([*record.labels, row.role]))
    return EmailFlag(
        email_id=row.email_id,
        record_id=record.record_id,
        role=row.role,
        duplicate=row.duplicate,
        duplicate_of=row.duplicate_of,
        cluster_size=len(record.evidence),
        sender=row.sender,
        subject=row.subject,
        date=row.date,
        amount_paise=row.amount_paise,
        reference=row.reference,
        segment=record.segment,
        vertical=record.vertical,
        labels=labels,
        needs_review=record.needs_review or row.duplicate,
    )


def reassess_record(record: FlaggedRecord, *, today: date | None = None) -> FlaggedRecord:
    """Recompute deterministic rule timing after evidence arrives in a later sweep."""
    effective_today = today or date.today()
    entry = _entry_for(record.legal.rule_id, load_registry())
    legal = _legal(
        claim_type=record.claim_type,
        rule_id=record.legal.rule_id,
        rule_status=record.legal.rule_status,
        entry=entry,
        origin_date=record.transaction.origin_date,
        resolved_on=record.resolution.received_on,
        today=effective_today,
        kind=record.resolution.kind,
    )
    status, status_label = _status(
        resolution_received=record.resolution.received,
        compliance=legal.compliance,
        has_rule=record.legal.rule_id is not None,
        kind=record.resolution.kind,
    )
    risk_flags = [
        flag for flag in record.risk_flags
        if flag not in {"refund_not_received", "payment_not_received", "refund_late"}
    ]
    if not record.resolution.received:
        risk_flags.append("payment_not_received" if record.resolution.kind == "payment" else "refund_not_received")
    if legal.compliance == "late":
        risk_flags.append("refund_late")
    return record.model_copy(
        update={
            "legal": legal,
            "status": status,
            "status_label": status_label,
            "risk_flags": list(dict.fromkeys(risk_flags)),
            "recommended_actions": recommended_actions(
                claim_type=record.claim_type,
                status=status,
                resolution_received=record.resolution.received,
                compliance=legal.compliance,
                segment=record.segment,
            ),
        }
    )


__all__ = ["build_flagged_records", "project_email", "reassess_record"]
