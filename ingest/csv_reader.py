from __future__ import annotations

import csv
import io

from clean.normalize import normalize_row
from engine.transactions import TransactionModel

ALIASES = {
    "date": {"date", "transaction date", "txn date"},
    "narration": {"narration", "description", "remarks", "particulars"},
    "debit": {"debit", "withdrawal", "withdrawals", "dr"},
    "credit": {"credit", "deposit", "deposits", "cr"},
    "balance": {"balance", "closing balance"},
    "ref": {"reference", "reference number", "rrn", "utr", "ref no"},
}


def _map_headers(headers: list[str]) -> dict[str, str]:
    lowered = {header.strip().lower(): header for header in headers}
    mapping: dict[str, str] = {}
    for target, choices in ALIASES.items():
        found = next((lowered[choice] for choice in choices if choice in lowered), None)
        if found:
            mapping[target] = found
    if "date" not in mapping or "narration" not in mapping:
        raise ValueError("CSV needs a date and narration/description column")
    return mapping


def parse_csv(text: str, source: str = "csv-upload") -> list[TransactionModel]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV has no header row")
    mapping = _map_headers(reader.fieldnames)
    transactions: list[TransactionModel] = []
    for row_number, source_row in enumerate(reader, start=2):
        row = {target: source_row.get(column, "") for target, column in mapping.items()}
        if not any(value.strip() for value in row.values()):
            continue
        transactions.append(normalize_row(row, source, row_number))
    return transactions
