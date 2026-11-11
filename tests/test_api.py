from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_contract() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["mode"] == "demo"


def test_registry_contract() -> None:
    response = client.get("/v1/registry")
    assert response.status_code == 200
    assert len(response.json()["items"]) == 16
    assert {item["id"] for item in response.json()["items"]} >= {"R-001", "R-007", "R-016"}


def test_registry_entry_and_unknown_entry() -> None:
    entry = client.get("/v1/registry/R-001")
    assert entry.status_code == 200
    assert entry.json()["status"] == "Seeded"
    assert "clock.weekends_count" in entry.json()["unresolved"]
    assert client.get("/v1/registry/R-404").status_code == 404


def test_ingest_is_explicit_stub() -> None:
    body = client.post("/v1/ingest", json={"text": "synthetic demo"}).json()
    assert body["status"] == "stub"
    assert body["parse_report"]["accepted"] is False


def test_detect_is_explicit_stub() -> None:
    body = client.post("/v1/detect", json={"transactions": [{"amount_paise": 200000}]}).json()
    assert body["status"] == "stub"
    assert body["input_rows"] == 1


def test_payment_requires_confirmation_and_stamps_demo() -> None:
    payload = {"debit_date": "2026-11-03", "amount_paise": 200000}
    pending = client.post("/v1/compute/payment", json=payload).json()
    assert pending["status"] == "confirmation_required"
    payload["confirmed"] = True
    result = client.post("/v1/compute/payment", json=payload).json()
    assert result["stamp"] == "UNVERIFIED RULE"
    assert result["amount_paise"] == {"low": 0, "high": 0}
    assert "C5" in result["conflicts"]


def test_msme_unclaimed_and_claim_contracts() -> None:
    msme = client.post(
        "/v1/compute/msme",
        json={"acceptance_date": "2026-11-03", "amount_paise": 100000},
    )
    assert msme.status_code == 200
    assert msme.json()["illustrative"] is True
    assert client.get("/v1/unclaimed/guide").status_code == 200
    claim = client.post("/v1/claims/draft", json={"right_id": "R-001"})
    assert claim.status_code == 200
    assert claim.json()["stamp"] == "UNVERIFIED RULE"
