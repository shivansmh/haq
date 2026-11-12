"""Structured, evidence-first records for every flagged payment or invoice.

The ledger layer sits on top of the deterministic sweep: it collapses related
emails into one stable record, tracks whether the money actually came back, and
checks that outcome against the linked (and explicitly stamped) legal rule.
Nothing here calls a provider or writes to disk.
"""

from .build import build_flagged_records, project_email
from .models import EMAIL_SCHEMA_VERSION, RECORD_SCHEMA_VERSION, FlaggedRecord
from .summary import summarize_records

__all__ = [
    "EMAIL_SCHEMA_VERSION",
    "RECORD_SCHEMA_VERSION",
    "FlaggedRecord",
    "build_flagged_records",
    "project_email",
    "summarize_records",
]
