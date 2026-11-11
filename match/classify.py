from __future__ import annotations

import re

from engine.transactions import Channel, TransactionModel

RULES: tuple[tuple[Channel, tuple[str, ...]], ...] = (
    ("UPI", (r"\bupi\b", r"\bpaytm\b", r"\bphonepe\b", r"\bgpay\b")),
    ("ATM", (r"\batm\b", r"cash withdrawal", r"cash dispensed")),
    ("card_pos", (r"\bpos\b", r"point of sale", r"card purchase", r"visa", r"mastercard")),
    ("NACH_APBS", (r"\bnach\b", r"\bapbs\b", r"ach debit")),
    ("prepaid", (r"prepaid", r"wallet")),
)

REVERSAL_WORDS = ("reversal", "refund", "return", "rev", "reverted")


def classify(transaction: TransactionModel) -> TransactionModel:
    text = transaction.narration_clean.lower()
    channel: Channel = "other"
    for candidate, patterns in RULES:
        if any(re.search(pattern, text) for pattern in patterns):
            channel = candidate
            break
    return transaction.model_copy(update={"channel": channel})


def is_reversal_like(transaction: TransactionModel) -> bool:
    text = transaction.narration_clean.lower()
    return transaction.credit_paise > 0 and any(word in text for word in REVERSAL_WORDS)
