from __future__ import annotations

from fastapi.testclient import TestClient

from api.gmail_service import filter_and_extract_transactions, get_demo_email_corpus
from api.main import app
from engine.classifier import classify_prompt

client = TestClient(app)


def test_gmail_counts_are_exact_and_no_bodies_leave_sweep() -> None:
    corpus = get_demo_email_corpus()
    result = filter_and_extract_transactions(corpus)

    assert result["emails_scanned"] == len(corpus)
    assert result["noise_filtered"] + result["financial_alerts_found"] == len(corpus)
    assert result["violations_detected"] == len(result["candidates"])
    assert all("body" not in message for message in result["emails"])
    assert all("statutory_compensation" not in candidate for candidate in result["candidates"])


def test_candidate_values_are_derived_from_messages() -> None:
    result = filter_and_extract_transactions(get_demo_email_corpus())
    upi = next(candidate for candidate in result["candidates"] if candidate["channel"] == "UPI")

    assert upi["date"] == "2026-11-03"
    assert upi["reversal_date"] == "2026-11-09"
    assert upi["debit"] == 200000
    assert upi["ref"] == "431209845123"
    assert upi["evidence_status"] == "paired_reversal"


def test_unparseable_ingest_does_not_create_demo_transactions() -> None:
    body = client.post("/v1/ingest", json={"text": "this is not a statement"}).json()

    assert body["status"] == "unparseable"
    assert body["parse_report"]["accepted"] is False
    assert body["transactions"] == []


def test_seeded_registry_never_claims_verified_high_confidence() -> None:
    body = client.post(
        "/v1/compute/payment",
        json={
            "debit_date": "2026-11-03",
            "reversal_date": "2026-11-09",
            "amount_paise": 200000,
            "confirmed": True,
            "channel": "UPI",
        },
    ).json()

    assert body["stamp"] == "UNVERIFIED RULE"
    assert body["confidence"] == "Low"
    assert body["illustrative"] is True


def test_classifier_uses_cautious_language() -> None:
    body = classify_prompt("My UPI payment failed and money left my account")

    assert "appears related" in body["summary"]
    assert "entitles" not in body["summary"]
    assert "must reverse" not in body["summary"]
