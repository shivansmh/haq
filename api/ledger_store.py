"""Session-scoped, in-memory ledger that carries records across sweeps.

The sweeper is intentionally transient: no email body, token or record is ever
written to disk. But a single refund usually arrives in a *later* sweep than the
debit, so the process keeps a small per-session ledger in RAM. Records merge on
their stable `record_id`, which is derived from claim type, reference, amount,
merchant and origin date.

Privacy boundaries:
- the store key is the opaque Haq session id, never an email address;
- only the already-redacted structured record is kept, never a raw message;
- the store is bounded and entries expire with the Gmail session TTL.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from ledger.build import reassess_record
from ledger.models import FlaggedRecord

MAX_SESSIONS = 500
ENTRY_TTL_SECONDS = 3600.0


@dataclass
class _SessionLedger:
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    records: dict[str, dict[str, Any]] = field(default_factory=dict)
    index: dict[str, str] = field(default_factory=dict)


def _keys_for(record: dict[str, Any]) -> list[str]:
    record_id = str(record.get("record_id") or "")
    keys = ["record:" + record_id] if record_id else []
    keys.extend(str(key) for key in record.get("identity_keys") or [] if key)
    return list(dict.fromkeys(keys))


def _merge_unique(existing: list[Any], incoming: list[Any], key: Any) -> list[Any]:
    merged: list[Any] = []
    seen: dict[Any, int] = {}
    for item in [*existing, *incoming]:
        marker = key(item)
        if marker in seen:
            # Later evidence is more complete; replace in place, keep the order.
            merged[seen[marker]] = item
            continue
        seen[marker] = len(merged)
        merged.append(item)
    return merged


def _merge_record(previous: dict[str, Any], incoming: dict[str, Any], now: float) -> dict[str, Any]:
    """Keep the newest deterministic view while preserving history."""
    merged = {**previous, **incoming}

    old_tracking = previous.get("tracking") or {}
    new_tracking = incoming.get("tracking") or {}
    merged["tracking"] = {
        "first_seen_at": old_tracking.get("first_seen_at") or new_tracking.get("first_seen_at"),
        "last_seen_at": new_tracking.get("last_seen_at"),
        "sweep_count": max(int(old_tracking.get("sweep_count") or 0), 1)
        + max(int(new_tracking.get("sweep_count") or 1), 1),
    }

    merged["evidence"] = _merge_unique(
        list(previous.get("evidence") or []),
        list(incoming.get("evidence") or []),
        lambda row: row.get("email_id"),
    )
    merged["timeline"] = _merge_unique(
        list(previous.get("timeline") or []),
        list(incoming.get("timeline") or []),
        lambda row: (row.get("date"), row.get("event"), row.get("email_id")),
    )

    old_ai = previous.get("ai") or {}
    new_ai = incoming.get("ai") or {}
    if new_ai.get("status") != "ok" and old_ai.get("status") == "ok":
        merged["ai"] = {**old_ai, **{key: new_ai[key] for key in ("status",) if key in new_ai}}
    merged["labels"] = list(
        dict.fromkeys([*(previous.get("labels") or []), *(incoming.get("labels") or [])])
    )[:32]
    merged["identity_keys"] = list(
        dict.fromkeys(
            [
                *(previous.get("identity_keys") or []),
                *(incoming.get("identity_keys") or []),
            ]
        )
    )
    merged["risk_flags"] = list(
        dict.fromkeys([*(previous.get("risk_flags") or []), *(incoming.get("risk_flags") or [])])
    )
    merged["needs_review"] = bool(
        previous.get("needs_review") or incoming.get("needs_review")
    )
    old_transaction = previous.get("transaction") or {}
    new_transaction = incoming.get("transaction") or {}
    merged_transaction = {**old_transaction, **new_transaction}
    old_origin = old_transaction.get("origin_date")
    new_origin = new_transaction.get("origin_date")
    if old_origin and new_origin:
        try:
            preserve_old_origin = date.fromisoformat(old_origin) <= date.fromisoformat(new_origin)
        except (TypeError, ValueError):
            preserve_old_origin = True
        if preserve_old_origin:
            merged_transaction["origin_date"] = old_origin
            merged_transaction["origin_email_id"] = (
                old_transaction.get("origin_email_id") or new_transaction.get("origin_email_id")
            )
        else:
            merged_transaction["origin_email_id"] = new_transaction.get("origin_email_id")
    elif old_origin and not new_origin:
        merged_transaction["origin_date"] = old_origin
        merged_transaction["origin_email_id"] = old_transaction.get("origin_email_id")
    elif old_transaction.get("origin_email_id") and not new_transaction.get("origin_email_id"):
        merged_transaction["origin_email_id"] = old_transaction["origin_email_id"]
    merged_transaction["reference"] = new_transaction.get("reference") or old_transaction.get("reference")
    merged_transaction["merchant"] = old_transaction.get("merchant") or new_transaction.get("merchant")
    merged["transaction"] = merged_transaction
    if not new_transaction.get("origin_email_id"):
        if (previous.get("amount") or {}).get("value_paise") is not None:
            merged["amount"] = previous["amount"]

    old_resolution = previous.get("resolution") or {}
    new_resolution = incoming.get("resolution") or {}
    resolution_dates = [
        value for value in (old_resolution.get("received_on"), new_resolution.get("received_on")) if value
    ]
    received_on = max(resolution_dates) if resolution_dates else None
    origin_date = (merged.get("transaction") or {}).get("origin_date")
    days_to_resolution = None
    if origin_date and received_on:
        try:
            days_to_resolution = (date.fromisoformat(received_on) - date.fromisoformat(origin_date)).days
            if days_to_resolution < 0:
                days_to_resolution = None
        except (TypeError, ValueError):
            pass
    kind = new_resolution.get("kind") or old_resolution.get("kind") or "refund"
    noun = {"payment": "Payment", "cash": "Cash reversal", "refund": "Refund", "reversal": "Reversal"}.get(kind, "Refund")
    received = bool(old_resolution.get("received") or new_resolution.get("received"))
    merged["resolution"] = {
        **old_resolution,
        **new_resolution,
        "kind": kind,
        "received": received,
        "received_on": received_on,
        "days_to_resolution": days_to_resolution,
        "evidence_email_ids": list(dict.fromkeys([
            *(old_resolution.get("evidence_email_ids") or []),
            *(new_resolution.get("evidence_email_ids") or []),
        ])),
        "label": f"{noun} received" if received else f"{noun} not seen yet",
    }
    try:
        merged = reassess_record(FlaggedRecord.model_validate(merged)).model_dump(mode="json")
    except (TypeError, ValueError):
        # Keep the safe evidence merge if an older record cannot be revalidated.
        pass
    return merged


def _weak_resolution_match(ledger: _SessionLedger, incoming: dict[str, Any]) -> str | None:
    """Use amount+merchant only for one plausible pending record within 30 days."""
    resolution = incoming.get("resolution") or {}
    if not resolution.get("received") or not resolution.get("received_on"):
        return None
    amount = (incoming.get("amount") or {}).get("value_paise")
    transaction = incoming.get("transaction") or {}
    merchant = str(transaction.get("merchant") or "").strip().casefold()
    if amount is None or not merchant:
        return None
    try:
        resolved_on = date.fromisoformat(str(resolution["received_on"]))
    except ValueError:
        return None

    matches: list[str] = []
    for record_id, candidate in ledger.records.items():
        if candidate.get("claim_type") != incoming.get("claim_type"):
            continue
        if (candidate.get("resolution") or {}).get("received"):
            continue
        if (candidate.get("amount") or {}).get("value_paise") != amount:
            continue
        candidate_transaction = candidate.get("transaction") or {}
        if str(candidate_transaction.get("merchant") or "").strip().casefold() != merchant:
            continue
        if transaction.get("reference") and candidate_transaction.get("reference"):
            if str(transaction["reference"]).casefold() != str(candidate_transaction["reference"]).casefold():
                continue
        try:
            origin = date.fromisoformat(str(candidate_transaction.get("origin_date") or ""))
        except ValueError:
            continue
        if 0 <= (resolved_on - origin).days <= 30:
            matches.append(record_id)
    return matches[0] if len(matches) == 1 else None


class LedgerStore:
    def __init__(self, *, max_sessions: int = MAX_SESSIONS, ttl_seconds: float = ENTRY_TTL_SECONDS):
        self._sessions: dict[str, _SessionLedger] = {}
        self._lock = threading.Lock()
        self._max_sessions = max_sessions
        self._ttl = ttl_seconds

    def _prune(self, now: float) -> None:
        expired = [
            key
            for key, ledger in self._sessions.items()
            if now - ledger.updated_at > self._ttl
        ]
        for key in expired:
            self._sessions.pop(key, None)
        if len(self._sessions) <= self._max_sessions:
            return
        oldest = sorted(self._sessions, key=lambda key: self._sessions[key].updated_at)
        for key in oldest[: len(self._sessions) - self._max_sessions]:
            self._sessions.pop(key, None)

    def merge(self, session_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
        """Merge this sweep's records into the session ledger and return it."""
        now = time.time()
        with self._lock:
            self._prune(now)
            ledger = self._sessions.setdefault(session_id, _SessionLedger())
            for record in records:
                record_id = str(record.get("record_id") or "")
                if not record_id:
                    continue
                existing_id = next(
                    (ledger.index[key] for key in _keys_for(record) if key in ledger.index),
                    None,
                )
                if existing_id is None:
                    existing_id = _weak_resolution_match(ledger, record)
                previous = ledger.records.get(existing_id or "") or ledger.records.get(record_id)
                if previous is not None:
                    stable_id = str(previous.get("record_id"))
                    merged = _merge_record(previous, record, now)
                    merged["record_id"] = stable_id
                    # Re-key the merged record under the id the user already saw.
                    ledger.records.pop(existing_id or "", None)
                    ledger.records.pop(record_id, None)
                    ledger.records[stable_id] = merged
                else:
                    ledger.records[record_id] = record
            ledger.index = {}
            for stored_id, stored in ledger.records.items():
                for key in _keys_for(stored):
                    ledger.index.setdefault(key, stored_id)
            ledger.updated_at = now
            payload = self._payload(ledger)
        return payload

    def get(self, session_id: str) -> dict[str, Any]:
        now = time.time()
        with self._lock:
            self._prune(now)
            ledger = self._sessions.get(session_id)
            if ledger is None:
                return {
                    "schema_version": "haq.ledger.v1",
                    "records": [],
                    "summary": _summarize([]),
                    "updated_at": None,
                }
            return self._payload(ledger)

    def clear(self, session_id: str) -> bool:
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    @staticmethod
    def _payload(ledger: _SessionLedger) -> dict[str, Any]:
        records = sorted(
            ledger.records.values(),
            key=lambda record: (
                record.get("tracking", {}).get("last_seen_at") or "",
                record.get("record_id") or "",
            ),
            reverse=True,
        )
        return {
            "schema_version": "haq.ledger.v1",
            "records": records,
            "summary": _summarize(records),
            "updated_at": ledger.updated_at,
        }


def _summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    from ledger.summary import summarize_records

    return summarize_records(records)


GMAIL_LEDGERS = LedgerStore()


__all__ = ["GMAIL_LEDGERS", "LedgerStore"]
