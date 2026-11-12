from __future__ import annotations

import json

from api.main import healthz


def clear_groq_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    for name in (
        "LLM_ENABLED",
        "GROQ_API_KEY",
        "GROQ_SPEND_CAP_USD",
        "LLM_MODEL_TRIAGE",
        "LLM_MODEL_EXTRACT",
        "LLM_MODEL_RECHECK",
    ):
        monkeypatch.delenv(name, raising=False)


def test_groq_health_status_is_disabled_by_default(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    clear_groq_env(monkeypatch)
    assert healthz()["groq_status"] == "disabled"


def test_groq_health_status_explains_missing_key_and_zero_cap(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    clear_groq_env(monkeypatch)
    monkeypatch.setenv("LLM_ENABLED", "true")
    assert healthz()["groq_status"] == "missing_key"
    monkeypatch.setenv("GROQ_API_KEY", "synthetic-test-credential")
    assert healthz()["groq_status"] == "zero_spend_cap"


def test_groq_health_status_requires_supported_priced_models(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    clear_groq_env(monkeypatch)
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("GROQ_API_KEY", "synthetic-test-credential")
    monkeypatch.setenv("GROQ_SPEND_CAP_USD", "0.0123")
    monkeypatch.setenv("LLM_MODEL_EXTRACT", "unpriced-model")
    assert healthz()["groq_status"] == "unsupported_model"
    monkeypatch.setenv("LLM_MODEL_EXTRACT", "openai/gpt-oss-20b")
    assert healthz()["groq_status"] == "ready"
    serialized = json.dumps(healthz())
    assert "synthetic-test-credential" not in serialized
    assert "0.0123" not in serialized
