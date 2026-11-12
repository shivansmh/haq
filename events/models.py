from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


EventType = Literal[
    "debit",
    "payment_failed",
    "refund_promised",
    "refund_credited",
    "order_cancelled",
    "atm_cash_not_dispensed",
    "invoice_overdue",
]


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    email_id: str
    claim_type: str
    event_type: EventType
    amount_paise: int | None = Field(default=None, ge=0)
    reference: str | None = None
    event_date: date | None = None
    quote: str
    sender: str
    subject: str
    confidence: Literal["High", "Medium", "Low"]
    reasons: list[str] = Field(default_factory=list)
