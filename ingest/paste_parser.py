from __future__ import annotations

import re

from clean.normalize import normalize_row
from engine.transactions import TransactionModel

DATE = r"(?P<date>\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}-[A-Za-z]{3}-\d{4})"
AMOUNT = r"(?P<amount>[₹]?\d[\d,]*(?:\.\d{1,2})?)"
REF = r"(?:RRN|UTR|ref(?:erence)?)[\s:#-]*(?P<ref>\d{6,18})"
ALERT_PATTERN = re.compile(
    rf"(?i){DATE}.*?(?:debited|debit|paid|withdrawn).*?{AMOUNT}.*?(?:{REF})?"
)


def parse_alert_text(
    text: str, source: str = "pasted-alert"
) -> tuple[list[TransactionModel], list[str]]:
    transactions: list[TransactionModel] = []
    warnings: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = ALERT_PATTERN.search(line)
        if not match:
            if line.strip():
                warnings.append(f"line {line_number}: could not parse alert; retained for review")
            continue
        groups = match.groupdict()
        transactions.append(
            normalize_row(
                {
                    "date": groups["date"],
                    "narration": line,
                    "debit": groups["amount"],
                    "credit": "",
                    "ref": groups.get("ref") or "",
                    "parse_confidence": "0.8",
                },
                source,
                line_number,
            )
        )
    return transactions, warnings
