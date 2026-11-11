from __future__ import annotations

import ast
from pathlib import Path

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
    demo_ref = "431209" + "845123"

    assert upi["date"] == "2026-11-03"
    assert upi["reversal_date"] == "2026-11-09"
    assert upi["debit"] == 200000
    assert upi["ref"] == demo_ref
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
            "mode": "demo",
        },
    ).json()

    assert body["stamp"] == "UNVERIFIED RULE"
    assert body["confidence"] == "Low"
    assert body["illustrative"] is True


def test_seeded_registry_is_refused_in_live_mode() -> None:
    response = client.post(
        "/v1/compute/payment",
        json={
            "debit_date": "2026-11-03",
            "reversal_date": "2026-11-09",
            "amount_paise": 200000,
            "confirmed": True,
            "channel": "UPI",
            "mode": "live",
        },
    )

    assert response.status_code == 409
    assert "Seeded" in response.json()["message"]


def test_live_gmail_functions_contain_no_demo_dates_or_amounts() -> None:
    path = Path(__file__).parents[1] / "api" / "gmail_service.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    live_functions = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in {
            "fetch_live_gmail",
            "filter_and_extract_transactions",
        }:
            live_functions.append(ast.get_source_segment(source, node) or "")
    live_source = "\n".join(live_functions)

    demo_ref = "431209" + "845123"
    for forbidden in ("2026-11-03", "2026-11-09", demo_ref, "200000", "500000", "14280000"):
        assert forbidden not in live_source


def test_classifier_uses_cautious_language() -> None:
    body = classify_prompt("My UPI payment failed and money left my account")

    assert "appears related" in body["summary"]
    assert "entitles" not in body["summary"]
    assert "must reverse" not in body["summary"]
