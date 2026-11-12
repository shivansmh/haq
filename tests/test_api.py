from fastapi.testclient import TestClient

import api.main as main
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


def test_gmail_callback_returns_to_dashboard_sweep(monkeypatch) -> None:
    monkeypatch.setattr(main, "FRONTEND_URL", "https://shivansmh.github.io/haq")
    main.OAUTH_STATES["test-state"] = {"session_id": "session-1", "created_at": main.time.time()}
    monkeypatch.setattr(
        main,
        "exchange_code_for_tokens",
        lambda *args: {"access_token": "access-token", "expires_in": 3600},
    )

    response = client.get(
        "/v1/gmail/callback?code=oauth-code&state=test-state",
        follow_redirects=False,
    )

    assert response.status_code == 303
    location = response.headers["location"]
    assert location.startswith("https://shivansmh.github.io/haq/dashboard/sweep?gmail=connected&handoff=")
    assert "access-token" not in location
    assert "haq_session=" in response.headers["set-cookie"]
    handoff = location.split("handoff=", 1)[1]
    completed = client.post("/v1/gmail/handoff", json={"handoff": handoff})
    assert completed.status_code == 200
    assert completed.json()["session_token"]


def test_gmail_callback_does_not_duplicate_dashboard_path(monkeypatch) -> None:
    monkeypatch.setattr(main, "FRONTEND_URL", "https://shivansmh.github.io/haq/dashboard/sweep")
    main.OAUTH_STATES["test-state-2"] = {"session_id": "session-2", "created_at": main.time.time()}

    response = client.get(
        "/v1/gmail/callback?error=access_denied&state=test-state-2",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "https://shivansmh.github.io/haq/dashboard/sweep?gmail=denied"
