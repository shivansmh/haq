from __future__ import annotations

from copy import deepcopy
from datetime import date
from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from api.gmail_service import filter_and_extract_transactions, get_demo_email_corpus
from api.ledger_store import LedgerStore
from api.main import app
from cases.builder import build_cases
from engine.registry_loader import Registry, load_registry
from events.normalize import normalize_emails
from ledger.build import build_flagged_records
from llm.client import FakeClient
from llm.config import LLMSettings
from llm.ledger_assist import enrich_flagged_records


def address(local: str, domain: str) -> str:
    return local + chr(64) + domain


def demo_result() -> dict[str, Any]:
    return filter_and_extract_transactions(get_demo_email_corpus())


def message(mid: str, sender: str, subject: str, body: str, received: str) -> dict[str, str]:
    return {
        "id": mid,
        "sender": sender,
        "subject": subject,
        "snippet": body[:120],
        "body": body,
        "date": received,
    }


# ------------------------------------------------------------------ demo ledger


def test_demo_sweep_flags_one_record_per_transaction() -> None:
    result = demo_result()
    records = result["flagged_records"]
    assert len(records) == 4
    assert {record["schema_version"] for record in records} == {"haq.flag.v1"}
    assert all(record["record_id"].startswith("hf_") for record in records)
    assert all(record["identity_keys"] for record in records)
    assert all("body" not in record for record in records)


def test_related_emails_cluster_and_duplicates_fold() -> None:
    result = demo_result()
    upi = next(
        record for record in result["flagged_records"]
        if record["claim_type"] == "upi_failed_debited"
        and record["transaction"]["merchant"] == "Swiggy"
    )
    roles = [item["role"] for item in upi["evidence"]]
    assert roles.count("debit") == 2
    assert "failure" in roles and "refund" in roles
    duplicates = [item for item in upi["evidence"] if item["duplicate"]]
    assert len(duplicates) == 1
    assert "duplicate_emails" in upi["risk_flags"]
    assert upi["resolution"]["received"] is True
    assert upi["resolution"]["kind"] == "refund"


def test_gaming_and_business_records_are_labelled() -> None:
    result = demo_result()
    gaming = next(
        record for record in result["flagged_records"]
        if record["vertical"] == "gaming" and record["transaction"]["merchant"] == "Steam"
    )
    assert gaming["transaction"]["merchant"] == "Steam"
    assert gaming["resolution"]["received"] is True
    assert {"gaming", "refund-received"} <= set(gaming["labels"])

    business = next(record for record in result["flagged_records"] if record["segment"] == "business")
    assert business["claim_type"] == "msme_invoice_overdue"
    assert business["resolution"]["kind"] == "payment"
    assert business["resolution"]["received"] is True
    assert {"business", "msme_invoice_overdue"} <= set(business["labels"])


def test_every_flagged_email_has_structured_json() -> None:
    result = demo_result()
    structured = [email["structured"] for email in result["emails"] if email.get("structured")]
    assert structured
    assert {row["schema_version"] for row in structured} == {"haq.email.v1"}
    assert all(row["record_id"].startswith("hf_") for row in structured)
    assert all(row["cluster_size"] >= 1 for row in structured)


# ------------------------------------------------------------------ rules


def _verified_registry(rule_id: str = "R-001") -> Registry:
    entry = load_registry().get(rule_id)
    verified = entry.model_copy(
        update={
            "verification": entry.verification.model_copy(
                update={"status": "Verified", "confidence": "High"}
            )
        }
    )
    return Registry({rule_id: verified})


def _records_for(messages: list[dict[str, str]], registry: Registry) -> list[Any]:
    events = normalize_emails(messages)
    cases = build_cases(events, registry=registry, today=date(2026, 11, 12))
    return build_flagged_records(cases, registry=registry, today=date(2026, 11, 12))


def test_late_refund_is_compared_with_the_rule() -> None:
    registry = _verified_registry()
    reference = "UPIREF-TEST-101"
    records = _records_for(
        [
            message(
                "d1",
                address("alerts", "hdfcbank.net"),
                "UPI debit",
                f"Rs 700 debited via UPI. UPI Ref {reference}.",
                "Sun, 01 Nov 2026 10:00:00 +0530",
            ),
            message(
                "r1",
                address("alerts", "hdfcbank.net"),
                "Reversal credit",
                f"Rs 700 credited by UPI reversal. UPI Ref {reference}.",
                "Tue, 10 Nov 2026 10:00:00 +0530",
            ),
        ],
        registry,
    )
    assert len(records) == 1
    legal = records[0].legal
    assert legal.rule_verified is True
    assert legal.stamp == "VERIFIED RULE"
    assert legal.compliance == "late"
    assert legal.deadline_date == date(2026, 11, 2)
    assert legal.compensation.computed is True
    assert legal.compensation.amount_paise == 8 * 10000


def test_on_time_refund_is_not_treated_as_a_claim() -> None:
    registry = _verified_registry()
    reference = "UPIREF-TEST-102"
    records = _records_for(
        [
            message(
                "d1",
                address("alerts", "hdfcbank.net"),
                "UPI debit",
                f"Rs 700 debited via UPI. UPI Ref {reference}.",
                "Sun, 01 Nov 2026 10:00:00 +0530",
            ),
            message(
                "r1",
                address("alerts", "hdfcbank.net"),
                "Reversal credit",
                f"Rs 700 credited by UPI reversal. UPI Ref {reference}.",
                "Mon, 02 Nov 2026 10:00:00 +0530",
            ),
        ],
        registry,
    )
    legal = records[0].legal
    assert legal.compliance == "on_time"
    assert records[0].status == "resolved"
    assert legal.compensation.computed is True
    assert legal.compensation.amount_paise == 0


def test_unverified_rules_never_produce_a_verified_stamp() -> None:
    result = demo_result()
    for record in result["flagged_records"]:
        assert record["legal"]["stamp"] != "VERIFIED RULE"
        assert record["legal"]["rule_verified"] is False
        assert record["legal"]["compensation"]["computed"] is False


# ------------------------------------------------------------------ stable ids and tracking


def test_record_ids_are_stable_across_identical_sweeps() -> None:
    first = demo_result()["flagged_records"]
    second = demo_result()["flagged_records"]
    assert [record["record_id"] for record in first] == [record["record_id"] for record in second]


def test_later_refund_updates_the_original_flag() -> None:
    store = LedgerStore()
    first = demo_result()["flagged_records"]
    upi = next(record for record in first if record["claim_type"] == "upi_failed_debited")
    store.merge("session-a", [upi])

    # A later sweep contains only the refund email; its lone hash differs, but the
    # reference identity key reconnects it to the record the user already has.
    refund_only = [dict(upi)]
    refund_only[0]["record_id"] = "hf_different_hash"
    refund_only[0]["resolution"] = {
        **upi["resolution"],
        "received": True,
        "received_on": "2026-11-03",
    }
    refund_only[0]["tracking"] = {
        "first_seen_at": "2026-11-12T10:00:00+00:00",
        "last_seen_at": "2026-11-12T10:00:00+00:00",
        "sweep_count": 1,
    }
    merged = store.merge("session-a", refund_only)
    assert len(merged["records"]) == 1
    assert merged["records"][0]["record_id"] == upi["record_id"]
    assert merged["records"][0]["tracking"]["sweep_count"] == 2


def test_later_refund_only_sweep_keeps_origin_date_for_rule_assessment() -> None:
    store = LedgerStore()
    original = next(
        record for record in demo_result()["flagged_records"]
        if record["claim_type"] == "upi_failed_debited"
    )
    original["resolution"]["received"] = False
    original["resolution"]["received_on"] = None
    original["resolution"]["evidence_email_ids"] = []
    original["transaction"]["origin_date"] = "2026-11-03"
    original["transaction"]["origin_email_id"] = "debit-email"
    store.merge("session-refund-only", [original])

    later = deepcopy(original)
    later["record_id"] = "hf_refund_only"
    later["transaction"]["origin_date"] = "2026-11-09"
    later["transaction"]["origin_email_id"] = None
    later["resolution"].update(
        received=True,
        received_on="2026-11-09",
        evidence_email_ids=["refund-email"],
    )
    merged = store.merge("session-refund-only", [later])["records"]

    assert len(merged) == 1
    record = merged[0]
    assert record["transaction"]["origin_date"] == "2026-11-03"
    assert record["resolution"]["received_on"] == "2026-11-09"
    assert record["resolution"]["days_to_resolution"] == 6
    assert record["legal"]["compliance"] == "received_rule_unverified"


def test_demo_session_header_isolates_cross_origin_demo_ledgers() -> None:
    client = TestClient(app)
    first_id = str(uuid4())
    second_id = str(uuid4())
    first = client.post("/v1/gmail/demo", headers={"X-Haq-Demo-Session": first_id}).json()
    second = client.post("/v1/gmail/demo", headers={"X-Haq-Demo-Session": second_id}).json()

    assert [row["tracking"]["sweep_count"] for row in first["ledger"]["records"]] == [1] * 4
    assert [row["tracking"]["sweep_count"] for row in second["ledger"]["records"]] == [1] * 4


def test_store_clear_forgets_the_session() -> None:
    store = LedgerStore()
    store.merge("session-b", demo_result()["flagged_records"])
    assert store.get("session-b")["records"]
    assert store.clear("session-b") is True
    assert store.get("session-b")["records"] == []


# ------------------------------------------------------------------ API + Groq


def test_ledger_endpoints_merge_and_clear() -> None:
    client = TestClient(app)
    cookies = {"haq_session": "synthetic-ledger-api-session"}
    client.delete("/v1/gmail/ledger", cookies=cookies)

    first = client.post("/v1/gmail/demo", cookies=cookies)
    assert first.status_code == 200
    assert len(first.json()["ledger"]["records"]) == 4

    second = client.post("/v1/gmail/demo", cookies=cookies)
    counts = [record["tracking"]["sweep_count"] for record in second.json()["ledger"]["records"]]
    assert counts == [2, 2, 2, 2]

    ledger = client.get("/v1/gmail/ledger", cookies=cookies).json()
    assert ledger["summary"]["total_records"] == 4
    assert ledger["summary"]["business_records"] == 1
    assert ledger["summary"]["gaming_records"] == 1

    assert client.delete("/v1/gmail/ledger", cookies=cookies).json() == {"cleared": True}
    assert client.get("/v1/gmail/ledger", cookies=cookies).json()["records"] == []


def test_groq_ledger_labels_are_advisory_only() -> None:
    records = build_flagged_records(
        build_cases(normalize_emails(get_demo_email_corpus())),
        today=date(2026, 11, 12),
    )
    before = records[0]
    enriched, status = enrich_flagged_records(
        records,
        client=FakeClient(),
        settings=LLMSettings(enabled=True, api_key="synthetic"),
    )
    after = enriched[0]
    assert status == "ok"
    assert after.ai.status == "ok"
    assert "synthetic" in after.labels
    assert after.amount == before.amount
    assert after.legal == before.legal
    assert after.status == before.status
    assert after.record_id == before.record_id


def test_groq_ledger_schema_cannot_express_legal_fields() -> None:
    from llm.groq_client import LEDGER_SCHEMA

    properties = LEDGER_SCHEMA["properties"]
    assert LEDGER_SCHEMA["additionalProperties"] is False
    for forbidden in ("amount", "status", "legal", "compliance", "deadline", "resolution", "evidence"):
        assert forbidden not in properties
