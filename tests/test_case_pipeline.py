from __future__ import annotations

from datetime import date, timedelta

from cases.builder import build_cases
from claims.pack import build_claim_pack
from events.models import Event
from events.normalize import normalize_emails
from taxonomy.loader import load_taxonomy

DEMO_UPI_REF = "431209" + "845123"


def address(local: str, domain: str) -> str:
    return local + chr(64) + domain


def message(mid: str, sender: str, subject: str, body: str, received: str) -> dict[str, str]:
    return {"id": mid, "sender": sender, "subject": subject, "snippet": body[:100], "body": body, "date": received}


def test_taxonomy_contains_five_hackathon_live_types() -> None:
    catalog = load_taxonomy()
    assert {item.id for item in catalog.all()} == {
        "upi_failed_debited",
        "card_debited_order_unconfirmed",
        "order_cancelled_refund_delayed",
        "atm_cash_not_dispensed",
        "msme_invoice_overdue",
    }


def test_events_from_related_emails_become_one_open_case() -> None:
    events = normalize_emails([
        message("d1", address("alerts", "hdfcbank.net"), "UPI debit", f"Rs 700 debited via UPI. UPI Ref {DEMO_UPI_REF}.", "Mon, 02 Nov 2026 10:00:00 +0530"),
        message("f1", address("support", "phonepe.com"), "Payment failed", "UPI payment of Rs 700 failed; amount debited.", "Mon, 02 Nov 2026 10:01:00 +0530"),
    ])
    cases = build_cases(events, today=date(2026, 11, 12))
    assert len(cases) == 1
    assert cases[0].claim_type == "upi_failed_debited"
    assert cases[0].status == "open"
    assert cases[0].rule_status == "Seeded"
    assert cases[0].deadline is None
    assert cases[0].worth_review is False


def test_reversal_is_deduped_and_case_is_resolved_without_unverified_clock() -> None:
    events = normalize_emails([
        message("f1", address("support", "phonepe.com"), "Payment failed", "UPI payment of Rs 700 failed; amount debited.", "Mon, 02 Nov 2026 10:00:00 +0530"),
        message("r1", address("alerts", "hdfcbank.net"), "Reversal credit", "Reversal credit of Rs 700 via UPI Reversal.", "Thu, 05 Nov 2026 10:00:00 +0530"),
        message("r1", address("alerts", "hdfcbank.net"), "Reversal credit", "Reversal credit of Rs 700 via UPI Reversal.", "Thu, 05 Nov 2026 10:00:00 +0530"),
    ])
    cases = build_cases(events, today=date(2026, 11, 12))
    assert len(cases) == 1
    assert len(cases[0].events) == 2
    assert cases[0].status == "resolved_on_time"
    assert cases[0].deadline is None


def test_claim_pack_is_evidence_first_for_seeded_rule() -> None:
    events = normalize_emails([
        message("f1", address("support", "phonepe.com"), "Payment failed", "UPI payment of Rs 700 failed; amount debited.", "Mon, 02 Nov 2026 10:00:00 +0530"),
    ])
    case = build_cases(events, today=date(2026, 11, 12))[0]
    pack = build_claim_pack(case)
    assert pack["rule_status"] == "Seeded"
    assert pack["deadline"] is None
    assert "debit alert" in pack["evidence_checklist"]
    assert "Seeded" in pack["draft"]


def test_case_clustering_does_not_join_conflicting_refs_or_claim_types() -> None:
    day = date(2026, 11, 3)

    def event(event_id: str, claim_type: str, reference: str) -> Event:
        return Event(
            event_id=event_id,
            email_id=event_id,
            claim_type=claim_type,
            event_type="debit",
            amount_paise=200000,
            reference=reference,
            event_date=day,
            quote="Synthetic payment alert",
            sender=address("alerts", "example.test"),
            subject="Payment alert",
            confidence="High",
        )

    cases = build_cases([
        event("one", "upi_failed_debited", "UPI-111"),
        event("two", "upi_failed_debited", "UPI-222"),
        event("three", "msme_invoice_overdue", "UPI-111"),
    ], today=day)

    assert len(cases) == 3


def test_amount_only_clustering_requires_a_close_dated_signal() -> None:
    def event(event_id: str, received: date | None) -> Event:
        return Event(
            event_id=event_id,
            email_id=event_id,
            claim_type="upi_failed_debited",
            event_type="debit",
            amount_paise=200000,
            reference=None,
            event_date=received,
            quote="Synthetic payment alert",
            sender=address("alerts", "example.test"),
            subject="Payment alert",
            confidence="High",
        )

    day = date(2026, 11, 3)
    assert len(build_cases([event("one", day), event("two", day + timedelta(days=2))], today=day)) == 2
    assert len(build_cases([event("one", None), event("two", None)], today=day)) == 2
