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


_RESOLUTION_EVENTS = {"refund_credited", "payment_received"}
_PAYMENT_FAMILY = {
    "upi_failed_debited",
    "card_debited_order_unconfirmed",
    "order_cancelled_refund_delayed",
}


def _compatible_claims(left: str, right: str) -> bool:
    return left == right or (left in _PAYMENT_FAMILY and right in _PAYMENT_FAMILY)


def _primary_claim(events: list[Event]) -> str:
    claims = {event.claim_type for event in events}
    for claim_type in (
        "upi_failed_debited",
        "card_debited_order_unconfirmed",
        "order_cancelled_refund_delayed",
    ):
        if claim_type in claims:
            return claim_type
    return events[0].claim_type


# A debit alert, a payment-failure notice and a cancellation often describe one
# underlying payment but can land on different claim types (UPI vs card vs order).
# They may merge only when an exact reference or amount also matches in time.
def _status(events: list[Event], deadline: date | None) -> tuple[CaseStatus, date | None, int | None]:
    resolved = [event.event_date for event in events if event.event_type in _RESOLUTION_EVENTS and event.event_date]
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
    # Indexed grouping: a sweep of a few thousand messages would otherwise compare
    # every event with every group. Reference and amount are natural blocking keys.
    grouped: list[list[Event]] = []
    by_reference: dict[tuple[str, str], list[int]] = {}
    by_amount: dict[tuple[str, int], list[int]] = {}
    for event in _dedupe(events):
        candidate_indexes: list[int] = []
        if event.reference:
            claims = _PAYMENT_FAMILY if event.claim_type in _PAYMENT_FAMILY else (event.claim_type,)
            for claim_type in claims:
                candidate_indexes.extend(by_reference.get((claim_type, event.reference.casefold()), []))
        if event.amount_paise:
            claims = _PAYMENT_FAMILY if event.claim_type in _PAYMENT_FAMILY else (event.claim_type,)
            for claim_type in claims:
                candidate_indexes.extend(by_amount.get((claim_type, event.amount_paise), []))
        matching_index = None
        amount_matches: list[int] = []
        reference_matches: list[int] = []
        for index in dict.fromkeys(candidate_indexes):
            group = grouped[index]
            same_reference = bool(event.reference) and any(
                item.reference and item.reference.casefold() == event.reference.casefold() for item in group
            )
            same_amount = bool(event.amount_paise) and any(
                item.amount_paise == event.amount_paise for item in group if item.amount_paise
            )
            conflicting_reference = bool(event.reference) and any(
                item.reference and item.reference.casefold() != event.reference.casefold() for item in group
            )
            dates = [item.event_date for item in group if item.event_date]
            anchor_date = min(dates) if dates else None
            if same_reference:
                close_in_time = (
                    anchor_date is None
                    or event.event_date is None
                    or abs((event.event_date - anchor_date).days) <= 30
                )
            else:
                has_resolution = event.event_type in _RESOLUTION_EVENTS or any(
                    item.event_type in _RESOLUTION_EVENTS for item in group
                )
                window = 30 if has_resolution else 1
                close_in_time = bool(anchor_date and event.event_date) and any(
                    abs((event.event_date - item.event_date).days) <= window
                    for item in group if item.event_date
                )
            amount_fallback = same_amount and not conflicting_reference
            compatible = all(_compatible_claims(event.claim_type, item.claim_type) for item in group)
            if compatible and close_in_time and same_reference:
                reference_matches.append(index)
            elif compatible and close_in_time and amount_fallback:
                amount_matches.append(index)
        if reference_matches:
            matching_index = reference_matches[0]
        elif len(amount_matches) == 1:
            # Amounts alone are weak identity. Join only when there is one
            # plausible nearby case; otherwise keep the events separate.
            matching_index = amount_matches[0]
        if matching_index is None:
            grouped.append([event])
            matching_index = len(grouped) - 1
        else:
            grouped[matching_index].append(event)
        if event.reference:
            by_reference.setdefault((event.claim_type, event.reference.casefold()), []).append(matching_index)
        if event.amount_paise:
            by_amount.setdefault((event.claim_type, event.amount_paise), []).append(matching_index)
    cases: list[Case] = []
    for raw_events in sorted(grouped, key=lambda group: (group[0].claim_type, group[0].event_id)):
        case_events = sorted(_dedupe(raw_events), key=lambda event: (event.event_date or date.min, event.event_id))
        claim_type = _primary_claim(case_events)
        rule_id, rule_status, offset = _clock_for(claim_type, taxonomy, registry)
        trigger_dates = [event.event_date for event in case_events if event.event_type not in _RESOLUTION_EVENTS and event.event_date]
        trigger_date = min(trigger_dates) if trigger_dates else None
        effective_today = today or date.today()
        deadline = trigger_date + timedelta(days=offset) if trigger_date and offset is not None else None
        resolved = [event.event_date for event in case_events if event.event_type in _RESOLUTION_EVENTS and event.event_date]
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
