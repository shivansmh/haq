from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TaxonomyModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DetectSpec(TaxonomyModel):
    sender_tiers: list[str] = Field(default_factory=list)
    positive_phrases: list[str] = Field(default_factory=list)
    negative_phrases: list[str] = Field(default_factory=list)
    required_fields: list[str] = Field(default_factory=list)


class LifecycleSpec(TaxonomyModel):
    trigger_event: str
    expected_resolution: str
    deadline_source: str


class TaxonomyClaimType(TaxonomyModel):
    id: str
    name: str
    who: Literal["consumer", "worker", "supplier"]
    detect: DetectSpec
    lifecycle: LifecycleSpec
    rule_id: str | None
    rule_status: Literal["Verified", "Seeded", "Parked", "Rejected", "None"]
    evidence: list[str]
    escalation: list[str]
    template: str
    eval_set: str


class TaxonomyCatalog:
    def __init__(self, entries: dict[str, TaxonomyClaimType]):
        self._entries = entries

    def all(self) -> list[TaxonomyClaimType]:
        return [self._entries[key] for key in sorted(self._entries)]

    def get(self, claim_type_id: str) -> TaxonomyClaimType:
        try:
            return self._entries[claim_type_id]
        except KeyError as exc:
            raise KeyError(f"Unknown claim type: {claim_type_id}") from exc

    def live(self) -> list[TaxonomyClaimType]:
        return [entry for entry in self.all() if entry.rule_status in {"Verified", "Seeded"}]
