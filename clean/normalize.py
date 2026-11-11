from __future__ import annotations

import hashlib
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from engine.transactions import TransactionModel

from .redact import redact_sensitive

DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y", "%d-%b-%Y", "%d-%m-%Y")


def parse_date(value: str) -> date:
    cleaned = value.strip()
    parsed: list[date] = []
    for fmt in DATE_FORMATS:
        try:
            parsed.append(datetime.strptime(cleaned, fmt).date())
        except ValueError:
            continue
    if len(parsed) != 1:
        raise ValueError(f"ambiguous or unsupported date: {value!r}")
    return parsed[0]


def parse_money(value: str | None) -> int:
    if not value or not value.strip():
        return 0
    cleaned = value.strip().replace(",", "").replace("₹", "")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    suffix = cleaned[-2:].lower() if len(cleaned) >= 2 else ""
    if suffix in {"dr", "cr"}:
        cleaned = cleaned[:-2].strip()
    try:
        paise = int((Decimal(cleaned) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except InvalidOperation as exc:
        raise ValueError(f"invalid money value: {value!r}") from exc
    return -paise if negative else paise


def clean_narration(value: str) -> str:
    return " ".join(redact_sensitive(value).split())


def make_txn_id(source: str, row_number: int) -> str:
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]
    return f"{digest}:{row_number}"


def normalize_row(row: dict[str, str], source: str, row_number: int) -> TransactionModel:
    narration = row.get("narration", "")
    raw = redact_sensitive(narration)
    debit = parse_money(row.get("debit"))
    credit = parse_money(row.get("credit"))
    confidence = float(row.get("parse_confidence", "1"))
    return TransactionModel(
        txn_id=make_txn_id(source, row_number),
        date=parse_date(row["date"]),
        narration_raw=raw,
        narration_clean=clean_narration(narration),
        debit_paise=max(debit, 0),
        credit_paise=max(credit, 0),
        balance_paise=parse_money(row.get("balance")) if row.get("balance") else None,
        ref=row.get("ref") or None,
        parse_confidence=confidence,
        source=source,
        source_row=row_number,
    )
