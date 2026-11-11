from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    code: str
    message: str
    field: str | None = None
    request_id: str


class RegistrySummary(BaseModel):
    id: str
    name: str
    status: Literal["Seeded", "Verified", "Parked", "Rejected"]
    confidence: Literal["High", "Medium", "Low"]


class ClassifyRequest(BaseModel):
    prompt: str
    filename: str | None = None


class ClassifyResponse(BaseModel):
    category: Literal["failed_payment", "msme_dues", "unclaimed_wealth", "general_rights"]
    confidence: float
    title: str
    summary: str
    statutory_law: str
    suggested_route: str
    extracted_entities: dict[str, Any]
    prompt: str


class GmailScanRequest(BaseModel):
    query: str | None = None
    max_results: int = Field(default=50, ge=1, le=100)


class IngestRequest(BaseModel):
    text: str | None = None
    filename: str | None = None
    file_bytes_base64: str | None = None
    password: str | None = None


class DetectRequest(BaseModel):
    transactions: list[dict[str, Any]] = Field(default_factory=list)


class PaymentComputeRequest(BaseModel):
    right_id: str = "R-001"
    debit_date: date
    reversal_date: date | None = None
    amount_paise: int = Field(gt=0)
    confirmed: bool = False
    channel: str = "UPI"
    mode: Literal["demo", "live"] = "demo"


class MsmeComputeRequest(BaseModel):
    acceptance_date: date
    payment_date: date | None = None
    amount_paise: int = Field(gt=0)
    written_agreement: bool = False
    agreed_days: int | None = Field(default=None, ge=0, le=45)


class GuideRequest(BaseModel):
    asset_types: list[str] = Field(default_factory=list)
    claimant_is_heir: bool = False


class ClaimDraftRequest(BaseModel):
    right_id: str
    confirmed_result: dict[str, Any] = Field(default_factory=dict)
    claimant_name: str = "Demo claimant"
    claimant_mobile: str | None = None
    claimant_email: str | None = None
    bank_name: str | None = None


class TraceStep(BaseModel):
    step: int
    text: str
    clause: str
    inputs: dict[str, Any] = Field(default_factory=dict)
