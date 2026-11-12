from __future__ import annotations

import time
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from api import main
from api.gmail_service import get_google_auth_url


def test_scan_checks_gmail_session_before_invalid_optional_llm_config(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("GROQ_API_KEY", "synthetic-test-credential")
    monkeypatch.setenv("GROQ_SPEND_CAP_USD", "not-a-number")
    response = TestClient(main.app).post("/v1/gmail/scan", json={"max_results": 1})
    assert response.status_code == 401
    assert response.json()["message"] == "Connect Gmail before starting a sweep"


def test_invalid_optional_llm_config_falls_back_to_deterministic_gmail_sweep(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("GROQ_API_KEY", "synthetic-test-credential")
    monkeypatch.setenv("GROQ_SPEND_CAP_USD", "not-a-number")
    session_id = "synthetic-session-id"
    now = time.time()
    main.GMAIL_SESSIONS[session_id] = {
        "access_token": "synthetic-google-token",
        "created_at": now,
        "last_seen": now,
        "expires_at": now + 3600,
    }
    observed: dict[str, object] = {}

    def fake_search(token, query, max_results, **kwargs):  # type: ignore[no-untyped-def]
        observed.update(kwargs)
        return {"status": "synthetic-ok"}

    monkeypatch.setattr(main, "search_gmail", fake_search)
    try:
        response = TestClient(main.app).post(
            "/v1/gmail/scan",
            json={"max_results": 1},
            cookies={main.SESSION_COOKIE: session_id},
        )
    finally:
        main.GMAIL_SESSIONS.pop(session_id, None)

    assert response.status_code == 200
    assert response.json()["status"] == "synthetic-ok"
    assert observed["llm_client"] is None
    assert observed["llm_settings"].enabled is False


def test_gmail_oauth_requests_readonly_scope_and_offline_consent() -> None:
    query = parse_qs(urlparse(get_google_auth_url("synthetic-client", "https://api.invalid/callback", "state")).query)
    assert query["scope"] == ["https://www.googleapis.com/auth/gmail.readonly"]
    assert query["access_type"] == ["offline"]
    assert query["prompt"] == ["consent"]
