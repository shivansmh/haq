from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from api.schemas import ClassifyResponse
from llm.client import DisabledClient, FakeClient
from llm.config import LLMSettings, load_settings
from llm.models import (
    AmountWithQuote,
    Channel,
    ExtractionResult,
    FieldStatus,
    FieldWithQuote,
    MessagePayload,
    Relevance,
    SignalType,
    TrustTier,
)
from llm.validate import LEGAL_CONCLUSION_PHRASES, validate_extraction


def message() -> MessagePayload:
    return MessagePayload(
        message_id="msg-synthetic-001",
        sender="synthetic-sender",
        subject="Payment alert",
        snippet="Rs 2,000 debited on 2026-01-02.",
        body_text="Rs 2,000 debited on 2026-01-02. Ref REF-ABC123.",
        received_at="2026-01-02T10:00:00Z",
    )


def valid_extraction() -> ExtractionResult:
    return ExtractionResult(
        message_id="msg-synthetic-001",
        relevance=Relevance.FINANCIAL_SIGNAL,
        signal_type=SignalType.DEBIT,
        amount=AmountWithQuote(
            value_paise=200000,
            source_quote="Rs 2,000",
            status=FieldStatus.PRESENT,
        ),
        transaction_reference=FieldWithQuote[str](
            value="REF-ABC123",
            source_quote="Ref REF-ABC123",
            status=FieldStatus.PRESENT,
        ),
        event_date=FieldWithQuote[date](
            value=date(2026, 1, 2),
            source_quote="2026-01-02",
            status=FieldStatus.PRESENT,
        ),
        reversal_date=FieldWithQuote[date](status=FieldStatus.ABSENT),
        channel=Channel.UPI,
        counterparty=None,
        explicit_failure_language=False,
        evidence_summary="Message contains a debit signal and an extracted event date.",
        needs_review=False,
        review_reasons=[],
        model_version="fake-v1",
        trust_tier=TrustTier.LLM_SUGGESTION,
    )


def test_config_defaults_are_disabled_and_frozen() -> None:
    settings = load_settings({})
    assert settings == LLMSettings()
    assert settings.enabled is False
    with pytest.raises((AttributeError, TypeError)):
        settings.enabled = True  # type: ignore[misc]


def test_config_reads_non_secret_values_and_rejects_negative_caps() -> None:
    settings = load_settings(
        {
            "LLM_ENABLED": "false",
            "LLM_PROVIDER": "fake",
            "LLM_TIMEOUT_SECONDS": "3.5",
            "LLM_MAX_MESSAGES_PER_SWEEP": "4",
            "LLM_MAX_MESSAGE_CHARS": "120",
        }
    )
    assert settings.provider == "fake"
    assert settings.timeout_seconds == 3.5
    assert settings.max_messages_per_sweep == 4
    with pytest.raises(ValueError, match="LLM_MAX_MESSAGE_CHARS"):
        load_settings({"LLM_MAX_MESSAGE_CHARS": "-1"})


def test_unknown_enums_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ExtractionResult(**(valid_extraction().model_dump() | {"relevance": "legal_conclusion"}))


def test_negative_amount_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AmountWithQuote(value_paise=-1, source_quote="Rs 0", status=FieldStatus.PRESENT)


def test_date_outside_configured_range_is_rejected() -> None:
    extraction = valid_extraction().model_copy(
        update={
            "event_date": FieldWithQuote[date](
                value=date(1900, 1, 1), source_quote="1900-01-01", status=FieldStatus.PRESENT
            )
        }
    )
    with pytest.raises(ValueError, match="configured range"):
        validate_extraction(extraction, message())


def test_amount_without_source_quote_is_rejected() -> None:
    with pytest.raises(ValidationError, match="source_quote"):
        AmountWithQuote(value_paise=200000, source_quote=None, status=FieldStatus.PRESENT)


def test_date_without_source_quote_is_rejected() -> None:
    with pytest.raises(ValidationError, match="source_quote"):
        FieldWithQuote[date](value=date(2026, 1, 2), source_quote=None, status=FieldStatus.PRESENT)


def test_missing_message_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        MessagePayload(
            message_id="",
            sender="sender",
            subject="subject",
            snippet="snippet",
            body_text="body",
        )


def test_overlong_quote_is_rejected() -> None:
    with pytest.raises(ValidationError):
        FieldWithQuote[str](
            value="x",
            source_quote="x" * 241,
            status=FieldStatus.PRESENT,
        )


def test_legal_conclusion_phrases_are_loaded_and_rejected() -> None:
    assert "you are entitled to compensation" in LEGAL_CONCLUSION_PHRASES
    assert len(LEGAL_CONCLUSION_PHRASES) == len(set(LEGAL_CONCLUSION_PHRASES))
    extraction = valid_extraction().model_copy(
        update={"evidence_summary": "The user is entitled to compensation."}
    )
    with pytest.raises(ValueError, match="legal-conclusion"):
        validate_extraction(extraction, message())


def test_source_quote_and_reference_must_be_in_message() -> None:
    validate_extraction(valid_extraction(), message())
    bad_quote = valid_extraction().model_copy(
        update={
            "amount": AmountWithQuote(
                value_paise=200000,
                source_quote="Rs 9,999",
                status=FieldStatus.PRESENT,
            )
        }
    )
    with pytest.raises(ValueError, match="source quote"):
        validate_extraction(bad_quote, message())
    bad_reference = valid_extraction().model_copy(
        update={
            "transaction_reference": FieldWithQuote[str](
                value="REF-NOT-IN-MESSAGE",
                source_quote="Ref REF-NOT-IN-MESSAGE",
                status=FieldStatus.PRESENT,
            )
        }
    )
    with pytest.raises(ValueError, match="reference"):
        validate_extraction(bad_reference, message())


def test_disabled_client_never_returns_data() -> None:
    result = DisabledClient().extract(message())
    assert result.llm_status == "disabled"
    assert result.result is None


def test_fake_client_valid_and_invalid_round_trips() -> None:
    valid = FakeClient().extract(message())
    assert valid.llm_status == "ok"
    assert valid.result is not None
    invalid = FakeClient(invalid=True).extract(message())
    assert invalid.llm_status == "invalid_output"
    assert invalid.result is None
    triage = FakeClient().triage(message())
    assert triage.llm_status == "ok"
    assert triage.result is not None


def test_api_llm_status_is_optional_and_enum_bounded() -> None:
    response = ClassifyResponse(
        category="failed_payment",
        confidence=0.0,
        title="Evidence review",
        summary="Deterministic parser only.",
        statutory_law="",
        suggested_route="review",
        extracted_entities={},
        prompt="synthetic",
    )
    assert response.llm_status is None
    response = response.model_copy(update={"llm_status": "disabled"})
    assert response.llm_status == "disabled"
    with pytest.raises(ValidationError):
        ClassifyResponse(
            **response.model_dump(exclude={"llm_status"}),
            llm_status="invented",
        )
