from __future__ import annotations

from datetime import date, timedelta
from hashlib import sha256

from engine.registry_loader import Registry, load_registry
from events.models import Event
from taxonomy.loader import load_taxonomy
from taxonomy.models import TaxonomyCatalog

from .models import Case, CaseStatus


def _dedupe(events: list[Event]) -> list[Event]:
    return list({event.event_id: event for event in events}.values())


def _clock_for(claim_type: str, taxonomy: TaxonomyCatalog, registry: Registry) -> tuple[str | None, str, int | None]:
    spec = taxonomy.get(claim_type)
    if not spec.rule_id:
        return None, spec.rule_status, None
    entry = registry.get(spec.rule_id)
    # Seeded and weaker entries may describe a possible rule, but must not
    # produce a deadline or compensation figure in the product.
    offset = entry.clock.offset if entry.status == "Verified" else None
    return spec.rule_id, entry.status, offset


def _status(events: list[Event], deadline: date | None) -> tuple[CaseStatus, date | None, int | None]:
    resolved = [event.event_date for event in events if event.event_type == "refund_credited" and event.event_date]
    resolved_on = max(resolved) if resolved else None
    if deadline is None:
        return ("resolved_on_time" if resolved_on else "open"), resolved_on, None
    if resolved_on is None:
        if date.today() <= deadline:
            return "open", None, None
        return "unresolved_past_deadline", None, (date.today() - deadline).days
    if resolved_on <= deadline:
        return "resolved_on_time", resolved_on, 0
    return "resolved_late", resolved_on, (resolved_on - deadline).days


def build_cases(
    events: list[Event],
    *,
    taxonomy: TaxonomyCatalog | None = None,
    registry: Registry | None = None,
    today: date | None = None,
) -> list[Case]:
    taxonomy = taxonomy or load_taxonomy()
    registry = registry or load_registry()
    grouped: list[list[Event]] = []
    for event in events:
        matching_group = None
        for candidate in grouped:
            anchor = candidate[0]
            same_claim = anchor.claim_type == event.claim_type
            same_reference = bool(anchor.reference and event.reference and anchor.reference == event.reference)
            same_amount = bool(anchor.amount_paise and event.amount_paise and anchor.amount_paise == event.amount_paise)
            dates = [item.event_date for item in candidate if item.event_date and event.event_date]
            close_in_time = not dates or any(abs((event.event_date - item_date).days) <= 30 for item_date in dates)
            if same_claim and close_in_time and (same_reference or same_amount):
                matching_group = candidate
                break
        if matching_group is None:
            grouped.append([event])
        else:
            matching_group.append(event)
    cases: list[Case] = []
    for raw_events in sorted(grouped, key=lambda group: (group[0].claim_type, group[0].event_id)):
        case_events = sorted(_dedupe(raw_events), key=lambda event: (event.event_date or date.min, event.event_id))
        claim_type = case_events[0].claim_type
        rule_id, rule_status, offset = _clock_for(claim_type, taxonomy, registry)
        trigger_dates = [event.event_date for event in case_events if event.event_type != "refund_credited" and event.event_date]
        trigger_date = min(trigger_dates) if trigger_dates else None
        effective_today = today or date.today()
        deadline = trigger_date + timedelta(days=offset) if trigger_date and offset is not None else None
        resolved = [event.event_date for event in case_events if event.event_type == "refund_credited" and event.event_date]
        resolved_on = max(resolved) if resolved else None
        if deadline is None:
            status: CaseStatus = "resolved_on_time" if resolved_on else "open"
            days_overdue = None
        elif resolved_on is None:
            status = "open" if effective_today <= deadline else "unresolved_past_deadline"
            days_overdue = None if status == "open" else (effective_today - deadline).days
        elif resolved_on <= deadline:
            status, days_overdue = "resolved_on_time", 0
        else:
            status, days_overdue = "resolved_late", (resolved_on - deadline).days
        case_id = sha256(f"{claim_type}:{','.join(event.event_id for event in case_events)}".encode()).hexdigest()[:16]
        cases.append(Case(
            case_id=case_id,
            claim_type=claim_type,
            rule_id=rule_id,
            rule_status=rule_status,
            events=case_events,
            amount_paise=next((event.amount_paise for event in case_events if event.amount_paise is not None), None),
            reference=next((event.reference for event in case_events if event.reference), None),
            deadline=deadline,
            resolved_on=resolved_on,
            days_overdue=days_overdue,
            status=status,
        ))
    return cases
