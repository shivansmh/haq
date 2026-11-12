from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class LLMSettings:
    """Validated provider configuration; disabled and bounded by default."""

    provider: str = "groq"
    api_base_url: str | None = None
    api_key: str | None = None
    model: str = "unset"
    timeout_seconds: float = 20.0
    max_messages_per_sweep: int = 100
    max_message_chars: int = 8000
    enabled: bool = False
    spend_cap_usd: float = 0.0
    triage_model: str = "openai/gpt-oss-20b"
    extract_model: str = "openai/gpt-oss-20b"
    recheck_model: str = "openai/gpt-oss-20b"
    ledger_model: str = "openai/gpt-oss-20b"
    triage_enabled: bool = True
    audit_sample_rate: float = 0.02
    max_records_per_sweep: int = 25


def _read_bool(raw: str, name: str) -> bool:
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def _read_positive_int(raw: str, name: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _read_positive_float(raw: str, name: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _read_nonnegative_float(raw: str, name: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be zero or greater")
    return value


def _read_rate(raw: str, name: str) -> float:
    value = _read_nonnegative_float(raw, name)
    if value > 1:
        raise ValueError(f"{name} must be between zero and one")
    return value


def load_settings(environ: Mapping[str, str] | None = None) -> LLMSettings:
    """Read environment settings, using safe defaults and failing on invalid values."""
    source = os.environ if environ is None else environ
    enabled = _read_bool(source.get("LLM_ENABLED", "false"), "LLM_ENABLED")
    provider = source.get("LLM_PROVIDER", "groq").strip()
    if not provider:
        raise ValueError("LLM_PROVIDER must not be empty")
    base_url = source.get("LLM_API_BASE_URL", "").strip() or None
    if base_url is not None and urlparse(base_url).scheme not in {"http", "https"}:
        raise ValueError("LLM_API_BASE_URL must use http or https")
    api_key = (source.get("GROQ_API_KEY", "").strip() or source.get("LLM_API_KEY", "").strip()) or None
    model = source.get("LLM_MODEL", "unset").strip() or "unset"
    settings = LLMSettings(
        provider=provider,
        api_base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_seconds=_read_positive_float(
            source.get("LLM_TIMEOUT_SECONDS", "20"), "LLM_TIMEOUT_SECONDS"
        ),
        max_messages_per_sweep=_read_positive_int(
            source.get("LLM_MAX_MESSAGES_PER_SWEEP", "100"), "LLM_MAX_MESSAGES_PER_SWEEP"
        ),
        max_message_chars=_read_positive_int(
            source.get("LLM_MAX_MESSAGE_CHARS", "8000"), "LLM_MAX_MESSAGE_CHARS"
        ),
        enabled=enabled,
        spend_cap_usd=_read_nonnegative_float(source.get("GROQ_SPEND_CAP_USD", "0"), "GROQ_SPEND_CAP_USD"),
        triage_model=source.get("LLM_MODEL_TRIAGE", "openai/gpt-oss-20b").strip(),
        extract_model=source.get("LLM_MODEL_EXTRACT", "openai/gpt-oss-20b").strip(),
        recheck_model=source.get("LLM_MODEL_RECHECK", "openai/gpt-oss-20b").strip(),
        ledger_model=source.get("LLM_MODEL_LEDGER", "openai/gpt-oss-20b").strip(),
        triage_enabled=_read_bool(source.get("LLM_TRIAGE_ENABLED", "true"), "LLM_TRIAGE_ENABLED"),
        audit_sample_rate=_read_rate(source.get("SWEEP_AUDIT_SAMPLE_RATE", "0.02"), "SWEEP_AUDIT_SAMPLE_RATE"),
        max_records_per_sweep=_read_positive_int(
            source.get("LLM_MAX_RECORDS_PER_SWEEP", "25"), "LLM_MAX_RECORDS_PER_SWEEP"
        ),
    )
    if settings.enabled and settings.api_key is None:
        raise ValueError("GROQ_API_KEY is required when LLM_ENABLED=true")
    return settings
