from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RECORD_SCHEMA_VERSION = "haq.flag.v1"
EMAIL_SCHEMA_VERSION = "haq.email.v1"

RecordStatus = Literal["action_needed", "tracking", "resolved", "reference_only"]
Segment = Literal["consumer", "business"]
Vertical = Literal[
    "gaming",
    "ecommerce",
    "food_delivery",
    "travel",
    "utilities",
    "business",
    "finance",
    "other",
]
Compliance = Literal[
    "on_time",
    "late",
    "received_rule_unverified",
    "not_due_yet",
    "not_received_past_deadline",
    "not_received_rule_unverified",
    "unknown",
]
ResolutionKind = Literal["refund", "reversal", "cash", "payment", "none"]
RuleStamp = Literal["VERIFIED RULE", "UNVERIFIED RULE", "NO RULE"]
EvidenceRole = Literal[
    "debit",
    "failure",
    "refund",
    "payment",
    "cancellation",
    "atm_failure",
    "invoice",
    "duplicate",
    "other",
]


class LedgerModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Money(LedgerModel):
    value_paise: int | None = Field(default=None, ge=0)
    currency: Literal["INR"] = "INR"
    display: str


class TransactionInfo(LedgerModel):
    reference: str | None = None
    channel: str = ""
    merchant: str | None = None
    origin_date: dt.date | None = None
    origin_email_id: str | None = None


class Resolution(LedgerModel):
    kind: ResolutionKind = "none"
    received: bool = False
    received_on: dt.date | None = None
    days_to_resolution: int | None = Field(default=None, ge=0)
    evidence_email_ids: list[str] = Field(default_factory=list)
    label: str


class Compensation(LedgerModel):
    computed: bool = False
    amount_paise: int | None = Field(default=None, ge=0)
    indicative_paise: int | None = Field(default=None, ge=0)
    daily_rate_paise: int | None = Field(default=None, ge=0)
    note: str


class LegalAssessment(LedgerModel):
    rule_id: str | None = None
    rule_status: str = "None"
    rule_verified: bool = False
    stamp: RuleStamp = "NO RULE"
    statutory_days: int | None = Field(default=None, ge=0)
    deadline_date: dt.date | None = None
    indicative_deadline_date: dt.date | None = None
    days_overdue: int | None = Field(default=None, ge=0)
    compliance: Compliance = "unknown"
    compliance_label: str
    compensation: Compensation
    citation: str | None = None
    note: str


class Tracking(LedgerModel):
    first_seen_at: dt.datetime
    last_seen_at: dt.datetime
    sweep_count: int = Field(default=1, ge=1)


class AIEnrichment(LedgerModel):
    status: str = "disabled"
    model: str | None = None
    summary: str | None = None
    merchant: str | None = None
    vertical: Vertical | None = None
    segment: Segment | None = None
    labels: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    needs_review: bool = False


class EvidenceEmail(LedgerModel):
    email_id: str
    role: EvidenceRole = "other"
    duplicate: bool = False
    duplicate_of: str | None = None
    date: dt.date | None = None
    sender: str
    subject: str
    quote: str
    amount_paise: int | None = Field(default=None, ge=0)
    reference: str | None = None


class TimelineItem(LedgerModel):
    date: dt.date | None = None
    event: str
    email_id: str
    amount_paise: int | None = Field(default=None, ge=0)


class FlaggedRecord(LedgerModel):
    """One transaction or invoice, with every related email and its outcome."""

    schema_version: Literal["haq.flag.v1"] = RECORD_SCHEMA_VERSION
    record_id: str
    # Stable matching hints used by the session store so a refund seen in a later
    # sweep updates this record even if that email alone yields a different hash.
    identity_keys: list[str] = Field(default_factory=list)
    case_id: str
    title: str
    claim_type: str
    category_label: str
    segment: Segment
    vertical: Vertical
    status: RecordStatus
    status_label: str
    amount: Money
    transaction: TransactionInfo
    resolution: Resolution
    legal: LegalAssessment
    labels: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    evidence: list[EvidenceEmail] = Field(default_factory=list)
    timeline: list[TimelineItem] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    ai: AIEnrichment = Field(default_factory=AIEnrichment)
    tracking: Tracking
    needs_review: bool = False
    safety_note: str = (
        "Haq reports what the linked rule says. This is an evidence record, not legal advice."
    )


class EmailFlag(LedgerModel):
    """Compact per-email JSON so every flagged email has its own structured row."""

    schema_version: Literal["haq.email.v1"] = EMAIL_SCHEMA_VERSION
    email_id: str
    record_id: str
    role: EvidenceRole = "other"
    duplicate: bool = False
    duplicate_of: str | None = None
    cluster_size: int = Field(default=1, ge=1)
    sender: str
    subject: str
    date: dt.date | None = None
    amount_paise: int | None = Field(default=None, ge=0)
    reference: str | None = None
    segment: Segment
    vertical: Vertical
    labels: list[str] = Field(default_factory=list)
    needs_review: bool = False
