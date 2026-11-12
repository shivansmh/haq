from __future__ import annotations

from api.gmail_service import filter_and_extract_transactions
from llm.client import FakeClient
from llm.config import LLMSettings
from llm.groq_client import GroqClient
from llm.models import LLMStatus


class CountingFakeClient(FakeClient):
    def __init__(self) -> None:
        super().__init__()
        self.seen: list[str] = []

    def extract(self, payload):  # type: ignore[no-untyped-def]
        self.seen.append(payload.message_id)
        return super().extract(payload)


def synthetic_contact() -> str:
    return "".join(("98", "765", "432", "10"))


def messages() -> list[dict[str, str]]:
    contact = synthetic_contact()
    return [
        {
            "id": "synthetic-email-001",
            "sender": "alerts" + "@" + "example.invalid",
            "subject": "Synthetic payment alert",
            "date": "Fri, 02 Jan 2026 10:00:00 +0000",
            "snippet": f"Rs 2,000 debited from account {contact}.",
            "body": f"Synthetic fixture. Rs 2,000 debited on 2026-01-02. Ref REF-ABC123. Contact {contact}.",
            "is_real": True,
        },
        {
            "id": "synthetic-email-002",
            "sender": "offers" + "@" + "example.invalid",
            "subject": "Sale, discount and coupon",
            "date": "Fri, 02 Jan 2026 10:00:00 +0000",
            "snippet": "Promotional offer.",
            "body": "Synthetic marketing message.",
            "is_real": False,
        },
    ]


def test_assistance_only_receives_prefiltered_redacted_messages_and_does_not_change_candidates() -> None:
    corpus = messages()
    client = CountingFakeClient()
    deterministic = filter_and_extract_transactions(corpus)
    assisted = filter_and_extract_transactions(
        corpus,
        llm_client=client,
        llm_settings=LLMSettings(max_messages_per_sweep=1),
    )

    assert client.seen == ["synthetic-email-001"]
    assert assisted["emails_scanned"] == deterministic["emails_scanned"]
    assert assisted["noise_filtered"] == deterministic["noise_filtered"]
    assert assisted["financial_alerts_found"] == deterministic["financial_alerts_found"]
    assert assisted["candidates"] == deterministic["candidates"]
    assert assisted["ai_assisted_count"] == 1
    assert assisted["emails"][0]["llm_assistance"]["trust_tier"] == "T-B"
    assert assisted["emails"][0]["llm_assistance"]["suggestions"]["amount_paise"]["value"] == 200000
    serialized = str(assisted)
    assert synthetic_contact() not in serialized
    assert "body'" not in serialized
    assert "body_text" not in serialized


def test_disabled_assistance_preserves_deterministic_only_mode() -> None:
    result = filter_and_extract_transactions(messages())
    assert result["llm_status"] == "disabled"
    assert result["ai_assisted_count"] == 0
    assert all("llm_assistance" not in message for message in result["emails"])


def test_unknown_model_cannot_bypass_spend_preflight_or_reach_network() -> None:
    import httpx

    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(500)

    client = GroqClient(
        api_key="test-only-key",
        extract_model="unpriced-model",
        spend_cap_usd=1,
        transport=httpx.MockTransport(handler),
    )
    result = client.extract(
        __import__("llm.models", fromlist=["MessagePayload"]).MessagePayload(
            message_id="synthetic-001",
            sender="synthetic sender",
            subject="synthetic subject",
            snippet="Rs 2,000 debited",
            body_text="Synthetic fixture Rs 2,000 debited on 2026-01-02",
        )
    )
    assert result.llm_status == LLMStatus.UNAVAILABLE
    assert result.error == "unsupported_model"
    assert calls == []
