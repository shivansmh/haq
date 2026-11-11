from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Status = Literal["Seeded", "Verified", "Parked", "Rejected"]
Confidence = Literal["High", "Medium", "Low"]
ClockUnit = Literal["calendar_days", "business_days", "months"]
AmountType = Literal["flat_per_day", "compound_multiple_of_bank_rate", "none"]


class RegistryModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(RegistryModel):
    instrument: str
    clause: str | None
    url: str | None
    tier: int = Field(ge=1, le=7)
    publication_date: date | None
    date_read: date


class Trigger(RegistryModel):
    event_type: str
    description: str


class Clock(RegistryModel):
    start_event: str | None
    offset: int | None
    unit: ClockUnit | None
    weekends_count: bool | None
    holidays_count: bool | None
    reversal_day_counts: bool | None


class Amount(RegistryModel):
    type: AmountType
    parameters: dict[str, Any]
    cap_paise: int | None


class EscalationStep(RegistryModel):
    level: int = Field(ge=1)
    channel: str
    url: str | None
    when_to_use: str


class Verification(RegistryModel):
    last_verified: date
    confidence: Confidence
    status: Status
    peer_checker: str | None


class WorkedExample(RegistryModel):
    name: str
    inputs: dict[str, Any]
    expected_outputs: dict[str, Any]
    peer_checker: str | None


class RightEntry(RegistryModel):
    id: str
    name: str
    beneficiary: str
    obligated_party: str
    sources: list[Source]
    trigger: Trigger
    clock: Clock
    amount: Amount
    exceptions: list[str]
    escalation_ladder: list[EscalationStep]
    evidence_needed: list[str]
    claim_time_limit: str | None
    verification: Verification
    worked_examples: list[WorkedExample]
    open_questions: list[str]
    conflict_ids: list[str]

    @field_validator("id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        if not value.startswith("R-") or len(value) != 5 or not value[2:].isdigit():
            raise ValueError("registry IDs must use the R-000 format")
        return value

    @property
    def status(self) -> Status:
        return self.verification.status

    @property
    def confidence(self) -> Confidence:
        return self.verification.confidence

    def unresolved_fields(self) -> list[str]:
        unresolved: list[str] = []
        for field in ("clock", "amount", "verification"):
            values = getattr(self, field).model_dump()
            for key, value in values.items():
                if value is None:
                    unresolved.append(f"{field}.{key}")
        for index, source in enumerate(self.sources):
            for key, value in source.model_dump().items():
                if value is None:
                    unresolved.append(f"sources[{index}].{key}")
        if self.claim_time_limit is None:
            unresolved.append("claim_time_limit")
        return unresolved
