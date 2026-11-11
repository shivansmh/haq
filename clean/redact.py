from __future__ import annotations

import re

PAN_PATTERN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
AADHAAR_PATTERN = re.compile(r"(?<!\d)(?:\d[ -]?){12}(?!\d)")
ACCOUNT_PATTERN = re.compile(r"(?<!\d)\d{9,18}(?!\d)")


def redact_sensitive(text: str) -> str:
    """Redact PAN, Aadhaar-shaped values and long account-like runs in memory."""
    redacted = PAN_PATTERN.sub("[PAN REDACTED]", text)
    redacted = AADHAAR_PATTERN.sub("[ID REDACTED]", redacted)
    return ACCOUNT_PATTERN.sub("[ACCOUNT REDACTED]", redacted)
