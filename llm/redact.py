from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


class SensitiveInputError(ValueError):
    """Raised when input contains a credential-like value that must not proceed."""


class OAuthTokenDetected(SensitiveInputError):
    """Raised when an access or refresh token shape appears in input."""


PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
AADHAAR_PATTERN = re.compile(r"(?<!\d)\d{4}(?:[ -]?\d{4}){2}(?!\d)")
PHONE_PATTERN = re.compile(r"(?<!\d)[6-9]\d{9}(?!\d)")
ACCOUNT_PATTERN = re.compile(r"(?<!\d)\d{9,18}(?!\d)")
CARD_PATTERN = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
EMAIL_PATTERN = re.compile(
    r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])",
    re.IGNORECASE,
)
UPI_CONTEXT_PATTERN = re.compile(
    r"(?i)\b(?:upi|vpa|pay(?:ment)?\s*(?:id|address))\b[^\n]{0,30}?"
    r"(?P<value>[a-z0-9][a-z0-9._-]{1,63}@[a-z][a-z0-9._-]{1,63})"
)
UPI_HANDLE_PATTERN = re.compile(
    r"(?i)(?<![\w.-])[a-z0-9][a-z0-9._-]{1,63}@"
    r"(?:okaxis|okhdfcbank|okicici|oksbi|okbizaxis|ybl|ibl|paytm|upi)(?![\w.-])"
)
UPI_GENERIC_PATTERN = re.compile(
    r"(?i)(?<![\w.-])[a-z0-9][a-z0-9._-]{1,63}@[a-z][a-z0-9_-]{1,63}(?![\w.-])"
)
AMOUNT_PATTERN = re.compile(
    r"(?i)(?:₹|rs\.?|inr)\s*[0-9][0-9,]*(?:\.[0-9]{1,2})?"
)
DATE_PATTERN = re.compile(
    r"\b(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b"
)
REFERENCE_PATTERN = re.compile(
    r"(?i)\b(?:reference|ref|rrn|transaction\s*(?:id|ref)?|txn\s*(?:id|ref)?)\b"
    r"\s*(?:number|no\.?|[:#-])?\s*"
    r"(?P<value>[a-z0-9][a-z0-9_-]{5,39})"
)
SLASH_REFERENCE_PATTERN = re.compile(r"(?<!\d)/\s*(?P<value>\d{12})\s*/(?!\d)")
OAUTH_PATTERN = re.compile(
    r"(?ix)(?:\bBearer\s+[A-Za-z0-9._~+/=-]{20,}|"
    r"\bya29\.[A-Za-z0-9._-]{20,}|\b1//[A-Za-z0-9._-]{20,}|"
    r"\b(?:access_token|refresh_token)\s*[=:]\s*[A-Za-z0-9._~+/=-]{20,})"
)


@dataclass(frozen=True, slots=True)
class _Candidate:
    start: int
    end: int
    label: str


@dataclass(frozen=True, slots=True)
class RedactionResult:
    """Redacted text plus an in-memory-only map for provenance checks."""

    redacted_text: str
    token_map: Mapping[str, str]

    def restore(self, value: str) -> str:
        """Restore redaction placeholders in a provider quote for local checking."""
        restored = value
        for token, original in self.token_map.items():
            restored = restored.replace(token, original)
        return restored


def _spans(pattern: re.Pattern[str], text: str, group: str | None = None) -> list[tuple[int, int]]:
    matches = pattern.finditer(text)
    if group is None:
        return [match.span() for match in matches]
    return [match.span(group) for match in matches]


def _overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(start < other_end and end > other_start for other_start, other_end in spans)


def _protected_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for pattern, group in (
        (AMOUNT_PATTERN, None),
        (DATE_PATTERN, None),
        (REFERENCE_PATTERN, "value"),
        (SLASH_REFERENCE_PATTERN, "value"),
    ):
        spans.extend(_spans(pattern, text, group))
    return spans


def _candidates(text: str) -> list[_Candidate]:
    patterns = (
        ("PAN", PAN_PATTERN, None),
        ("CARD", CARD_PATTERN, None),
        ("AADHAAR", AADHAAR_PATTERN, None),
        ("UPI", UPI_CONTEXT_PATTERN, "value"),
        ("UPI", UPI_HANDLE_PATTERN, None),
        ("UPI", UPI_GENERIC_PATTERN, None),
        ("EMAIL", EMAIL_PATTERN, None),
        ("PHONE", PHONE_PATTERN, None),
        ("ACCOUNT", ACCOUNT_PATTERN, None),
    )
    return [
        _Candidate(start, end, label)
        for label, pattern, group in patterns
        for start, end in _spans(pattern, text, group)
    ]


def _replace_sensitive(text: str) -> RedactionResult:
    protected = _protected_spans(text)
    selected: list[_Candidate] = []
    for candidate in sorted(_candidates(text), key=lambda item: (item.start, -(item.end - item.start))):
        if _overlaps(candidate.start, candidate.end, protected):
            continue
        if _overlaps(candidate.start, candidate.end, [(item.start, item.end) for item in selected]):
            continue
        selected.append(candidate)

    counters: dict[str, int] = {}
    token_map: dict[str, str] = {}
    redacted = text
    for candidate in sorted(selected, key=lambda item: item.start, reverse=True):
        counters[candidate.label] = counters.get(candidate.label, 0) + 1
        token = f"<{candidate.label}_{counters[candidate.label]}>"
        original = text[candidate.start : candidate.end]
        token_map[token] = original
        redacted = redacted[: candidate.start] + token + redacted[candidate.end :]
    return RedactionResult(redacted, MappingProxyType(token_map))


def redact_sensitive(text: str) -> RedactionResult:
    """Reject credentials and redact identifiers without touching financial evidence."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if OAUTH_PATTERN.search(text):
        raise OAuthTokenDetected("OAuth token-shaped input is not accepted")
    return _replace_sensitive(text)


__all__ = [
    "OAuthTokenDetected",
    "RedactionResult",
    "SensitiveInputError",
    "redact_sensitive",
]
