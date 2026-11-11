from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Channel = Literal["UPI", "ATM", "card_pos", "NACH_APBS", "prepaid", "other"]
PairLabel = Literal["reversed", "ambiguous", "unreversed"]
MatchStrength = Literal["High", "Medium", "Low"]


class TransactionModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    txn_id: str
    date: date
    narration_raw: str
    narration_clean: str
    debit_paise: int = Field(ge=0)
    credit_paise: int = Field(ge=0)
    balance_paise: int | None = None
    channel: Channel = "other"
    ref: str | None = None
    parse_confidence: float = Field(ge=0, le=1)
    source: str
    source_row: int = Field(ge=1)


class PairMatch(BaseModel):
    debit_txn_id: str
    credit_txn_id: str | None
    strength: MatchStrength | None
    label: PairLabel
    reason: str
    days_after: int | None


class ParseReport(BaseModel):
    source: str
    rows_seen: int
    rows_emitted: int
    warnings: list[str]
    running_balance_ok: bool | None


class Candidate(BaseModel):
    transaction: TransactionModel
    match: PairMatch
    requires_confirmation: bool = True
