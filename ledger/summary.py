from __future__ import annotations

from typing import Any


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Totals the UI can trust without re-deriving legal status."""
    refunds_received = 0
    refunds_late = 0
    action_needed = 0
    business = 0
    gaming = 0
    total_paise = 0
    for record in records:
        amount = record.get("amount") or {}
        value = amount.get("value_paise")
        if isinstance(value, int):
            total_paise += value
        resolution = record.get("resolution") or {}
        if resolution.get("received"):
            refunds_received += 1
        legal = record.get("legal") or {}
        if legal.get("compliance") == "late":
            refunds_late += 1
        if record.get("status") == "action_needed":
            action_needed += 1
        if record.get("segment") == "business":
            business += 1
        if record.get("vertical") == "gaming":
            gaming += 1
    return {
        "total_records": len(records),
        "total_amount_paise": total_paise,
        "refunds_received": refunds_received,
        "refunds_pending": len(records) - refunds_received,
        "refunds_late": refunds_late,
        "action_needed": action_needed,
        "business_records": business,
        "gaming_records": gaming,
    }


__all__ = ["summarize_records"]
