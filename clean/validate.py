from __future__ import annotations

from engine.transactions import TransactionModel


def running_balance_ok(transactions: list[TransactionModel]) -> bool | None:
    """Validate known consecutive balances; return None when there is no pair to check."""
    ordered = sorted(transactions, key=lambda item: item.source_row)
    checked = 0
    for previous, current in zip(ordered, ordered[1:]):
        if previous.balance_paise is None or current.balance_paise is None:
            continue
        checked += 1
        expected = previous.balance_paise - current.debit_paise + current.credit_paise
        if expected != current.balance_paise:
            return False
    return bool(checked) if checked else None


def dedupe_transactions(transactions: list[TransactionModel]) -> list[TransactionModel]:
    """Drop exact overlap duplicates while preserving the first occurrence."""
    seen: set[tuple[object, ...]] = set()
    unique: list[TransactionModel] = []
    for transaction in transactions:
        key = (
            transaction.date,
            transaction.debit_paise,
            transaction.credit_paise,
            transaction.ref,
            transaction.narration_clean,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(transaction)
    return unique
