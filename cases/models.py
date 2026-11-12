from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from events.models import Event


CaseStatus = Literal["open", "resolved_on_time", "resolved_late", "unresolved_past_deadline"]


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    claim_type: str
    rule_id: str | None
    rule_status: str
    events: list[Event]
    amount_paise: int | None = Field(default=None, ge=0)
    reference: str | None = None
    deadline: date | None = None
    resolved_on: date | None = None
    days_overdue: int | None = Field(default=None, ge=0)
    status: CaseStatus

    @property
    def worth_review(self) -> bool:
        return self.status in {"resolved_late", "unresolved_past_deadline"}
