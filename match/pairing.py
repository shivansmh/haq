from __future__ import annotations

from difflib import SequenceMatcher

from engine.transactions import Candidate, PairMatch, TransactionModel
from match.classify import is_reversal_like

SUPPORTED = {"UPI", "ATM", "card_pos", "NACH_APBS", "prepaid"}


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left.lower(), right.lower()).ratio()


def pair_all(
    transactions: list[TransactionModel], window_days: int = 30
) -> list[Candidate]:
    debits = [item for item in transactions if item.debit_paise > 0 and item.channel in SUPPORTED]
    credits = [item for item in transactions if item.credit_paise > 0 and is_reversal_like(item)]
    candidates: list[Candidate] = []
    for debit in debits:
        matches: list[tuple[int, TransactionModel, str, float]] = []
        for credit in credits:
            days_after = (credit.date - debit.date).days
            if (
                days_after < 0
                or days_after > window_days
                or credit.credit_paise != debit.debit_paise
            ):
                continue
            same_ref = debit.ref and credit.ref and debit.ref == credit.ref
            similarity = _similarity(debit.narration_clean, credit.narration_clean)
            if same_ref:
                matches.append((days_after, credit, "High", 1.0))
            elif similarity >= 0.45:
                matches.append((days_after, credit, "Medium", similarity))
            else:
                matches.append((days_after, credit, "Low", similarity))
        if not matches:
            match = PairMatch(
                debit_txn_id=debit.txn_id, credit_txn_id=None, strength=None, label="unreversed",
                reason="No same-amount credit found within the pairing window", days_after=None,
            )
        else:
            days_after, credit, strength, _ = sorted(
                matches, key=lambda item: (item[2] != "High", item[0])
            )[0]
            label = "reversed"
            match = PairMatch(
                debit_txn_id=debit.txn_id, credit_txn_id=credit.txn_id, strength=strength,
                label=label, reason=f"{strength} same-amount match", days_after=days_after,
            )
        candidates.append(Candidate(transaction=debit, match=match))
    return candidates


def pair_transactions(
    transactions: list[TransactionModel], window_days: int = 30
) -> list[Candidate]:
    """Return user-facing candidates; on-time reversals are intentionally hidden."""
    return [
        candidate
        for candidate in pair_all(transactions, window_days)
        if candidate.match.label != "reversed" or (candidate.match.days_after or 0) > 1
    ]
