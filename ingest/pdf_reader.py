from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pdfplumber
from pydantic import BaseModel

from clean.normalize import normalize_row, parse_money
from clean.validate import running_balance_ok
from engine.transactions import ParseReport, TransactionModel
from match.classify import classify

MONEY = re.compile(r"\(?[\d,]+\.\d{2}\)?")
REFERENCE = re.compile(r"(?:UPI|UPI REV)/(?P<ref>\d{12})/")
DATE_PATTERNS = {
    "alpha": re.compile(r"^\d{2}/\d{2}/\d{4}\b"),
    "beta": re.compile(r"^\d{2}-[A-Za-z]{3}-\d{2}\b"),
    "gamma": re.compile(r"^\d{2} [A-Za-z]{3} \d{4}\b"),
    "delta": re.compile(r"^\d{4}-\d{2}-\d{2}\b"),
}
class PdfParseResult(BaseModel):
    transactions: list[TransactionModel]
    report: ParseReport
    layout: str


def detect_layout(text: str) -> str:
    if "Txn Date" in text:
        return "beta"
    if "Amount (INR)" in text:
        return "delta"
    if "Date Details Amount Balance" in text:
        return "gamma"
    if "Date Narration Debit Credit Balance" in text:
        return "alpha"
    raise ValueError("unsupported statement layout: no known header signature")


def scan_text(text: str) -> list[str]:
    patterns = {
        "pan": r"\b[A-Z]{5}\d{4}[A-Z]\b",
        "aadhaar_grouped": r"\b\d{4} \d{4} \d{4}\b",
        "email": r"[\w.+-]+@[\w-]+\.[\w.]+",
        "phone": r"\b[6-9]\d{9}\b",
        "long_digits": r"(?<!/)\b\d{9,18}\b(?!/)",
    }
    scrubbed = re.sub(r"/\d{12}/", "/REF/", text)
    return [label for label, pattern in patterns.items() if re.search(pattern, scrubbed)]


def scan_pdf(path: Path) -> list[str]:
    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    return scan_text(text)


def _is_date_line(line: str, layout: str) -> bool:
    return bool(DATE_PATTERNS[layout].match(line))


def _logical_rows(lines: list[str], layout: str) -> list[str]:
    rows: list[str] = []
    current: list[str] = []
    for line in lines:
        line = line.strip()
        if not line or "SYNTHETIC TEST DATA" in line or line.startswith("Closing balance:"):
            continue
        if _is_date_line(line, layout):
            if current:
                rows.append(" ".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        rows.append(" ".join(current))
    return rows


def _parse_logical_row(
    line: str, layout: str, previous_balance: int | None
) -> dict[str, str] | None:
    date_text = DATE_PATTERNS[layout].match(line)
    if not date_text:
        return None
    date_value = date_text.group(0)
    rest = line[len(date_value) :].strip()
    if "OPENING BALANCE" in rest.upper():
        return None
    amounts = MONEY.findall(rest)
    if len(amounts) < 2:
        return None
    movement_text, balance_text = amounts[-2], amounts[-1]
    narration = rest
    for value in amounts:
        narration = narration.replace(value, " ", 1)
    narration = re.sub(r"\b(?:Dr|Cr)\b", " ", narration, flags=re.IGNORECASE)
    narration = " ".join(narration.split())
    movement = movement_text.replace("(", "").replace(")", "")
    balance = balance_text.replace("(", "").replace(")", "")
    debit = ""
    credit = ""
    if layout == "gamma":
        marker = re.search(r"\b(Dr|Cr)\b", rest, flags=re.IGNORECASE)
        if marker and marker.group(1).lower() == "dr":
            debit = movement
        else:
            credit = movement
    elif layout == "delta" and movement_text.startswith("("):
        debit = movement
    elif previous_balance is not None:
        if parse_money(balance) < previous_balance:
            debit = movement
        else:
            credit = movement
    else:
        debit = movement
    reference = REFERENCE.search(narration)
    return {
        "date": date_value,
        "narration": narration,
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "ref": reference.group("ref") if reference else "",
        "parse_confidence": "0.95",
    }


def parse_pdf(path: Path) -> PdfParseResult:
    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    transactions: list[TransactionModel] = []
    warnings: list[str] = []
    layout: str | None = None
    previous_balance: int | None = None
    row_number = 0
    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if layout is None:
                layout = detect_layout(text)
            for logical in _logical_rows(text.splitlines(), layout):
                row = _parse_logical_row(logical, layout, previous_balance)
                if row is None:
                    if "OPENING BALANCE" in logical.upper():
                        opening = MONEY.findall(logical)
                        if opening:
                            previous_balance = parse_money(opening[-1])
                    else:
                        warnings.append(f"page {page_number}: could not parse row: {logical}")
                    continue
                row_number += 1
                source = f"{file_hash}:page-{page_number}"
                transaction = classify(normalize_row(row, source, row_number))
                transactions.append(transaction)
                previous_balance = transaction.balance_paise
    if layout is None:
        raise ValueError(f"PDF contains no extractable text: {path}")
    report = ParseReport(
        source=file_hash,
        rows_seen=row_number,
        rows_emitted=len(transactions),
        warnings=warnings,
        running_balance_ok=running_balance_ok(transactions),
    )
    return PdfParseResult(transactions=transactions, report=report, layout=layout)
