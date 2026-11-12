from __future__ import annotations

from datetime import date

from cases.builder import build_cases
from claims.pack import build_claim_pack
from events.normalize import normalize_emails
from taxonomy.loader import load_taxonomy


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
        message("d1", "alerts@hdfcbank.net", "UPI debit", "Rs 700 debited via UPI. UPI Ref 431209845123.", "Mon, 02 Nov 2026 10:00:00 +0530"),
        message("f1", "support@phonepe.com", "Payment failed", "UPI payment of Rs 700 failed; amount debited.", "Mon, 02 Nov 2026 10:01:00 +0530"),
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
        message("f1", "support@phonepe.com", "Payment failed", "UPI payment of Rs 700 failed; amount debited.", "Mon, 02 Nov 2026 10:00:00 +0530"),
        message("r1", "alerts@hdfcbank.net", "Reversal credit", "Reversal credit of Rs 700 via UPI Reversal.", "Thu, 05 Nov 2026 10:00:00 +0530"),
        message("r1", "alerts@hdfcbank.net", "Reversal credit", "Reversal credit of Rs 700 via UPI Reversal.", "Thu, 05 Nov 2026 10:00:00 +0530"),
    ])
    cases = build_cases(events, today=date(2026, 11, 12))
    assert len(cases) == 1
    assert len(cases[0].events) == 2
    assert cases[0].status == "resolved_on_time"
    assert cases[0].deadline is None


def test_claim_pack_is_evidence_first_for_seeded_rule() -> None:
    events = normalize_emails([
        message("f1", "support@phonepe.com", "Payment failed", "UPI payment of Rs 700 failed; amount debited.", "Mon, 02 Nov 2026 10:00:00 +0530"),
    ])
    case = build_cases(events, today=date(2026, 11, 12))[0]
    pack = build_claim_pack(case)
    assert pack["rule_status"] == "Seeded"
    assert pack["deadline"] is None
    assert "debit alert" in pack["evidence_checklist"]
    assert "Seeded" in pack["draft"]
