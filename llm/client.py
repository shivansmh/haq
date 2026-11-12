from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Generic, TypeVar

from .models import (
    AmountWithQuote,
    Channel,
    ExtractionResult,
    FieldStatus,
    FieldWithQuote,
    LedgerResult,
    LedgerSegment,
    LedgerVertical,
    LLMStatus,
    MessagePayload,
    Relevance,
    SignalType,
    TriageResult,
    TrustTier,
)
from .validate import validate_extraction

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class LLMResponse(Generic[T]):
    llm_status: LLMStatus
    result: T | None = None
    error: str | None = None


class LLMClient(ABC):
    """Provider-neutral interface; implementations must remain server-side."""

    @abstractmethod
    def triage(self, payload: MessagePayload) -> LLMResponse[TriageResult]:
        """Classify one already-prefiltered message without legal reasoning."""

    @abstractmethod
    def extract(self, payload: MessagePayload) -> LLMResponse[ExtractionResult]:
        """Extract quoted evidence from one already-prefiltered message."""

    @abstractmethod
    def ledger(self, payload: MessagePayload) -> LLMResponse[LedgerResult]:
        """Suggest human-readable labels for one deterministic flagged record."""


class DisabledClient(LLMClient):
    def triage(self, payload: MessagePayload) -> LLMResponse[TriageResult]:
        return LLMResponse(llm_status=LLMStatus.DISABLED)

    def extract(self, payload: MessagePayload) -> LLMResponse[ExtractionResult]:
        return LLMResponse(llm_status=LLMStatus.DISABLED)

    def ledger(self, payload: MessagePayload) -> LLMResponse[LedgerResult]:
        return LLMResponse(llm_status=LLMStatus.DISABLED)


class FakeClient(LLMClient):
    """Deterministic test double; it never contacts a provider."""

    def __init__(self, invalid: bool = False) -> None:
        self.invalid = invalid

    def triage(self, payload: MessagePayload) -> LLMResponse[TriageResult]:
        if self.invalid:
            return LLMResponse(llm_status=LLMStatus.INVALID_OUTPUT, error="fake invalid triage")
        return LLMResponse(
            llm_status=LLMStatus.OK,
            result=TriageResult(
                message_id=payload.message_id,
                relevance=Relevance.FINANCIAL_SIGNAL,
                signal_type=SignalType.DEBIT,
                evidence_summary="Message appears relevant for evidence review.",
                needs_review=True,
                review_reasons=["Fake client requires human confirmation."],
                trust_tier=TrustTier.LLM_SUGGESTION,
                model_version="fake-v1",
            ),
        )

    def extract(self, payload: MessagePayload) -> LLMResponse[ExtractionResult]:
        if self.invalid:
            return LLMResponse(llm_status=LLMStatus.INVALID_OUTPUT, error="amount cannot be negative")
        result = ExtractionResult(
            message_id=payload.message_id,
            relevance=Relevance.FINANCIAL_SIGNAL,
            signal_type=SignalType.DEBIT,
            amount=AmountWithQuote(
                value_paise=200000,
                source_quote="Rs 2,000",
                status=FieldStatus.PRESENT,
            ),
            transaction_reference=FieldWithQuote[str](status=FieldStatus.ABSENT),
            event_date=FieldWithQuote[date](status=FieldStatus.ABSENT),
            reversal_date=FieldWithQuote[date](status=FieldStatus.ABSENT),
            currency="INR",
            channel=Channel.UPI,
            counterparty=None,
            explicit_failure_language=False,
            evidence_summary="Message appears to contain a payment signal.",
            needs_review=True,
            review_reasons=["Fake output requires deterministic review."],
            model_version="fake-v1",
            trust_tier=TrustTier.LLM_SUGGESTION,
        )
        try:
            validate_extraction(result, payload)
        except ValueError as exc:
            return LLMResponse(llm_status=LLMStatus.INVALID_OUTPUT, error=str(exc))
        return LLMResponse(llm_status=LLMStatus.OK, result=result)

    def ledger(self, payload: MessagePayload) -> LLMResponse[LedgerResult]:
        if self.invalid:
            return LLMResponse(llm_status=LLMStatus.INVALID_OUTPUT, error="fake invalid ledger")
        return LLMResponse(
            llm_status=LLMStatus.OK,
            result=LedgerResult(
                record_id=payload.message_id,
                summary="Synthetic record for a deterministic test.",
                merchant=None,
                vertical=LedgerVertical.OTHER,
                segment=LedgerSegment.CONSUMER,
                labels=["synthetic", "payment"],
                needs_review=False,
                review_reasons=[],
                model_version="fake-v1",
            ),
        )


__all__ = ["DisabledClient", "FakeClient", "LLMClient", "LLMResponse"]
