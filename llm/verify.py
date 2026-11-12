from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal


class QuoteVerificationError(ValueError):
    """Raised when an extracted value cannot be proven by its supplied quote."""


class AmbiguousDateError(ValueError):
    """Raised when a numeric date has more than one plausible day/month order."""


DateConvention = Literal["DMY", "MDY"]
ValueKind = Literal["text", "amount", "date", "reference"]
TEXT_DATE_PATTERN = re.compile(
    r"\b(?:\d{1,2}[ -]+[A-Za-z]{3,9}[ ,-]+\d{4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})\b",
    re.IGNORECASE,
)


def normalise_whitespace(value: str) -> str:
    """Collapse all whitespace and apply case-folding for evidence matching."""
    return " ".join(value.casefold().split())


def normalise_currency_symbols(value: str) -> str:
    """Canonicalise common rupee spellings without deciding whether a value is valid."""
    value = value.replace("₹", " INR ")
    value = re.sub(r"\b(?:rs\.?|inr)\b", " INR ", value, flags=re.IGNORECASE)
    return normalise_whitespace(value)


def normalise_indian_digit_grouping(value: str) -> str:
    """Remove presentation grouping from digit runs, including Indian 12,34,567 style."""
    def ungroup(match: re.Match[str]) -> str:
        return match.group(0).replace(",", "").replace(" ", "")

    return re.sub(r"(?<![A-Za-z])\d[\d, ]*\d|(?<![A-Za-z])\d+", ungroup, value)


def normalise_reference(value: str) -> str:
    """Compare references independent of case, whitespace, punctuation, or separators."""
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _parse_amount_to_paise(value: str | int | Decimal) -> int:
    if isinstance(value, int):
        return value
    text = normalise_currency_symbols(str(value))
    text = re.sub(r"[^0-9.\-]", "", text)
    if not text or text.count(".") > 1:
        raise QuoteVerificationError(f"invalid amount: {value!r}")
    try:
        amount = Decimal(text)
    except InvalidOperation as exc:
        raise QuoteVerificationError(f"invalid amount: {value!r}") from exc
    if amount < 0:
        raise QuoteVerificationError("amount cannot be negative")
    return int(amount * 100)


def _amounts_in_text(value: str) -> list[int]:
    candidates = re.findall(
        r"(?:₹|\b(?:rs\.?|inr)\b)\s*[-+]?\s*\d[\d, ]*(?:\.\d{1,2})?",
        value,
        flags=re.IGNORECASE,
    )
    return [_parse_amount_to_paise(candidate) for candidate in candidates]


def normalise_date(value: str | date, sender_convention: DateConvention | None = None) -> date:
    """Parse an evidence date, rejecting ambiguous numeric day/month order by default."""
    if isinstance(value, date):
        return value
    text = value.strip()
    for fmt in (
        "%Y-%m-%d", "%Y/%m/%d", "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d/%b/%Y",
        "%b %d %Y", "%B %d %Y", "%b %d, %Y", "%B %d, %Y",
    ):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass

    match = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text)
    if not match:
        raise ValueError(f"unsupported date format: {value!r}")
    first, second, year = (int(part) for part in match.groups())
    if year < 100:
        year += 2000
    if first <= 12 and second <= 12 and first != second and sender_convention is None:
        raise AmbiguousDateError(f"ambiguous day/month date: {value!r}")
    if sender_convention == "DMY" or (sender_convention is None and first > 12):
        day, month = first, second
    elif sender_convention == "MDY" or (sender_convention is None and second > 12):
        month, day = first, second
    else:
        day, month = first, second
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise ValueError(f"invalid date: {value!r}") from exc


def _normalise_for_match(value: str) -> str:
    value = normalise_currency_symbols(value)
    value = normalise_indian_digit_grouping(value)
    return normalise_whitespace(value)


def _value_occurs_in_quote(extracted_value: object, quote: str, kind: ValueKind) -> bool:
    if kind == "amount":
        try:
            return _parse_amount_to_paise(extracted_value) in _amounts_in_text(quote)  # type: ignore[arg-type]
        except (TypeError, ValueError, QuoteVerificationError):
            return False
    if kind == "date":
        try:
            wanted = normalise_date(extracted_value)  # type: ignore[arg-type]
        except (TypeError, ValueError, AmbiguousDateError):
            return False
        for candidate in re.findall(r"\b\d{1,4}[/-]\d{1,2}[/-]\d{1,4}\b", quote):
            try:
                if normalise_date(candidate, sender_convention="DMY") == wanted:
                    return True
            except ValueError:
                continue
        for match in TEXT_DATE_PATTERN.finditer(quote):
            try:
                if normalise_date(match.group(0)) == wanted:
                    return True
            except (ValueError, AmbiguousDateError):
                continue
        return wanted.isoformat() in _normalise_for_match(quote)
    if kind == "reference":
        return normalise_reference(str(extracted_value)) in normalise_reference(quote)
    return normalise_whitespace(str(extracted_value)) in normalise_whitespace(quote)


def verify_quote(
    original_message: str,
    quote: str,
    extracted_value: object,
    *,
    kind: ValueKind = "text",
) -> bool:
    """Require both quote presence in the message and value presence inside the quote."""
    if not quote or not _normalise_for_match(quote) or _normalise_for_match(quote) not in _normalise_for_match(original_message):
        raise QuoteVerificationError("source quote is not present in the original message")
    if not _value_occurs_in_quote(extracted_value, quote, kind):
        raise QuoteVerificationError("extracted value is not present inside the source quote")
    return True


__all__ = [
    "AmbiguousDateError",
    "QuoteVerificationError",
    "normalise_currency_symbols",
    "normalise_date",
    "normalise_indian_digit_grouping",
    "normalise_reference",
    "normalise_whitespace",
    "verify_quote",
]
