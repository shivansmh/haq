from __future__ import annotations

import json
from pathlib import Path

import httpx

from eval.run import run
from llm.groq_client import GroqClient
from llm.models import LLMStatus, MessagePayload


def payload() -> MessagePayload:
    return MessagePayload(
        message_id="email-001",
        sender="Nivara Bank (invented)",
        subject="Synthetic alert",
        snippet="Rs 1,200 debited.",
        body_text="SYNTHETIC FIXTURE. Rs 1,200 debited on 2026-01-01. Reference SYN-REF-0001.",
    )


def response_for(body: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": json.dumps(body)}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        },
    )


def triage_body() -> dict:
    return {
        "message_id": "email-001",
        "relevance": "financial_signal",
        "signal_type": "debit",
        "evidence_summary": "Synthetic message appears relevant.",
        "needs_review": True,
        "review_reasons": ["Synthetic output requires review."],
        "trust_tier": "llm_suggestion",
        "model_version": "test-model",
    }


def test_zero_spend_cap_stops_before_network_request() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return response_for(triage_body())

    client = GroqClient(api_key="test-key", spend_cap_usd=0, transport=httpx.MockTransport(handler))
    result = client.triage(payload())
    assert result.llm_status == LLMStatus.UNAVAILABLE
    assert result.error == "spend cap exceeded before provider request"
    assert calls == []


def test_retry_then_success_and_payload_contains_only_synthetic_fields() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(503, json={"error": "temporary"})
        return response_for(triage_body())

    client = GroqClient(
        api_key="test-key",
        spend_cap_usd=1,
        max_retries=2,
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )
    result = client.triage(payload())
    assert result.llm_status == LLMStatus.OK
    assert len(calls) == 3
    body = calls[-1].content.decode()
    assert "test-key" not in body
    assert "ya29." not in body
    assert "SYNTHETIC FIXTURE" in body
    assert "Authorization" not in body


def test_timeout_maps_to_timeout_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    client = GroqClient(
        api_key="test-key",
        spend_cap_usd=1,
        max_retries=0,
        transport=httpx.MockTransport(handler),
    )
    result = client.triage(payload())
    assert result.llm_status == LLMStatus.TIMEOUT
    assert result.error == "provider_timeout"


def test_mock_evaluation_writes_required_metric_sections(tmp_path: Path) -> None:
    report = run(__import__("llm.client", fromlist=["FakeClient"]).FakeClient(), split="unseen")
    assert report["synthetic_only"] is True
    assert report["emails"] == 40
    for key in (
        "event_recall_precision_by_type",
        "event_recall_by_sender_template",
        "field_exact_match",
        "verified_quote_rate",
        "fabricated_field_rate",
        "fabricated_field_upper_bound",
        "unknown_rate",
        "review_rate",
        "unseen_template_recall",
        "injection_pass_rate",
        "calibration",
        "cost_per_100_emails_usd",
        "p50_latency_ms",
        "p95_latency_ms",
    ):
        assert key in report
