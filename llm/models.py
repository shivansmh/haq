from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LLMStatus(str, Enum):
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    INVALID_OUTPUT = "invalid_output"
    OK = "ok"


class TrustTier(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM_SUGGESTION = "llm_suggestion"
    USER_CONFIRMED = "user_confirmed"


class Relevance(str, Enum):
    FINANCIAL_SIGNAL = "financial_signal"
    POSSIBLE_NOISE = "possible_noise"
    UNKNOWN = "unknown"


class SignalType(str, Enum):
    DEBIT = "debit"
    REVERSAL = "reversal"
    FAILED_PAYMENT = "failed_payment"
    ATM_FAILURE = "atm_failure"
    INVOICE_OVERDUE = "invoice_overdue"
    REFUND = "refund"
    OTHER = "other"
    UNKNOWN = "unknown"


class FieldStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    AMBIGUOUS = "ambiguous"


class Currency(str, Enum):
    INR = "INR"
    UNKNOWN = "unknown"


class Channel(str, Enum):
    UPI = "UPI"
    ATM = "ATM"
    CARD = "CARD"
    NACH = "NACH"
    MSME = "MSME"
    OTHER = "OTHER"
    UNKNOWN = "unknown"


class LedgerVertical(str, Enum):
    GAMING = "gaming"
    ECOMMERCE = "ecommerce"
    FOOD_DELIVERY = "food_delivery"
    TRAVEL = "travel"
    UTILITIES = "utilities"
    BUSINESS = "business"
    FINANCE = "finance"
    OTHER = "other"


class LedgerSegment(str, Enum):
    CONSUMER = "consumer"
    BUSINESS = "business"


class MessagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message_id: str = Field(min_length=1, max_length=200)
    sender: str = Field(max_length=320)
    subject: str = Field(max_length=500)
    snippet: str = Field(max_length=2000)
    body_text: str = Field(max_length=8000)
    received_at: str | None = Field(default=None, max_length=100)


T = TypeVar("T")


class FieldWithQuote(BaseModel, Generic[T]):
    model_config = ConfigDict(extra="forbid")

    value: T | None = None
    source_quote: str | None = Field(default=None, max_length=240)
    status: FieldStatus = FieldStatus.ABSENT

    @field_validator("value")
    @classmethod
    def reject_negative_amounts(cls, value: T | None) -> T | None:
        if isinstance(value, int) and value < 0:
            raise ValueError("amount cannot be negative")
        return value

    @model_validator(mode="after")
    def validate_presence_and_quote(self) -> "FieldWithQuote[T]":
        if self.status == FieldStatus.PRESENT and self.value is None:
            raise ValueError("present fields require a value")
        if self.value is not None and self.status != FieldStatus.PRESENT:
            raise ValueError("a value requires status=present")
        if self.value is not None and not self.source_quote:
            raise ValueError("a value requires a source_quote")
        if self.status == FieldStatus.ABSENT and self.source_quote:
            raise ValueError("absent fields cannot contain a source_quote")
        return self


class AmountWithQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value_paise: int | None = None
    source_quote: str | None = Field(default=None, max_length=240)
    status: FieldStatus = FieldStatus.ABSENT

    @field_validator("value_paise")
    @classmethod
    def reject_negative_amounts(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("amount cannot be negative")
        return value

    @model_validator(mode="after")
    def validate_presence_and_quote(self) -> "AmountWithQuote":
        if self.status == FieldStatus.PRESENT and self.value_paise is None:
            raise ValueError("present fields require a value")
        if self.value_paise is not None and self.status != FieldStatus.PRESENT:
            raise ValueError("a value requires status=present")
        if self.value_paise is not None and not self.source_quote:
            raise ValueError("a value requires a source_quote")
        if self.status == FieldStatus.ABSENT and self.source_quote:
            raise ValueError("absent fields cannot contain a source_quote")
        return self


class Conflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(min_length=1, max_length=100)
    deterministic_value: str | int | date | None = None
    llm_value: str | int | date | None = None
    status: str = Field(default="conflict", pattern="^conflict$")
    action: str = Field(default="ask_user", pattern="^ask_user$")


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: SignalType
    event_date: date | None = None
    source_quote: str | None = Field(default=None, max_length=240)

    @model_validator(mode="after")
    def validate_event_quote(self) -> "Event":
        if self.event_date is not None and not self.source_quote:
            raise ValueError("event_date requires a source_quote")
        return self


class TriageResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=1)
    relevance: Relevance
    signal_type: SignalType
    evidence_summary: str = Field(max_length=500)
    needs_review: bool
    review_reasons: list[str] = Field(default_factory=list, max_length=10)
    trust_tier: TrustTier = TrustTier.LLM_SUGGESTION
    model_version: str = Field(min_length=1, max_length=100)


class LedgerResult(BaseModel):
    """Advisory labels for one flagged record. It cannot set legal fields or amounts."""

    model_config = ConfigDict(extra="forbid")

    record_id: str = Field(min_length=1, max_length=200)
    summary: str = Field(max_length=400)
    merchant: str | None = Field(default=None, max_length=120)
    vertical: LedgerVertical
    segment: LedgerSegment
    labels: list[str] = Field(default_factory=list, max_length=8)
    needs_review: bool
    review_reasons: list[str] = Field(default_factory=list, max_length=10)
    model_version: str = Field(min_length=1, max_length=100)


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=1, max_length=200)
    relevance: Relevance
    signal_type: SignalType
    amount: AmountWithQuote = Field(default_factory=AmountWithQuote)
    currency: Currency = Currency.UNKNOWN
    transaction_reference: FieldWithQuote[str] = Field(default_factory=FieldWithQuote[str])
    event_date: FieldWithQuote[date] = Field(default_factory=FieldWithQuote[date])
    reversal_date: FieldWithQuote[date] = Field(default_factory=FieldWithQuote[date])
    channel: Channel = Channel.UNKNOWN
    counterparty: str | None = Field(default=None, max_length=200)
    explicit_failure_language: bool
    evidence_summary: str = Field(max_length=500)
    needs_review: bool
    review_reasons: list[str] = Field(default_factory=list, max_length=10)
    conflicts: list[Conflict] = Field(default_factory=list, max_length=20)
    model_version: str = Field(min_length=1, max_length=100)
    trust_tier: TrustTier = TrustTier.LLM_SUGGESTION


__all__ = [
    "Channel",
    "Conflict",
    "Currency",
    "Event",
    "ExtractionResult",
    "AmountWithQuote",
    "FieldStatus",
    "FieldWithQuote",
    "LedgerResult",
    "LedgerSegment",
    "LedgerVertical",
    "LLMStatus",
    "MessagePayload",
    "Relevance",
    "SignalType",
    "TriageResult",
    "TrustTier",
]
