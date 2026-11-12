from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from .client import LLMClient, LLMResponse
from .models import ExtractionResult, LLMStatus, MessagePayload, TriageResult
from .prompts import build_prompt
from .validate import validate_extraction

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MAX_COMPLETION_TOKENS = 900
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_RETRIES = 2


class SpendCapExceeded(RuntimeError):
    """Raised before a provider request when the configured run cap is exhausted."""


@dataclass
class SpendBudget:
    cap_usd: float = 0.0
    spent_usd: float = 0.0

    def reserve_worst_case(self, input_tokens: int, output_tokens: int, input_rate: float, output_rate: float) -> None:
        estimate = (input_tokens / 1_000_000 * input_rate) + (output_tokens / 1_000_000 * output_rate)
        if self.spent_usd + estimate > self.cap_usd:
            raise SpendCapExceeded("configured Groq spend cap would be exceeded")

    def record(self, usage: dict[str, Any], input_rate: float, output_rate: float) -> None:
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        self.spent_usd += (prompt_tokens / 1_000_000 * input_rate) + (
            completion_tokens / 1_000_000 * output_rate
        )


@dataclass(frozen=True)
class GroqModelPricing:
    input_per_million: float
    output_per_million: float


PRICING = {
    "openai/gpt-oss-20b": GroqModelPricing(0.075, 0.30),
    "openai/gpt-oss-120b": GroqModelPricing(0.15, 0.60),
}


def _strict_string_enum(values: list[str]) -> dict[str, Any]:
    return {"type": "string", "enum": values}


TRIAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "message_id": {"type": "string"},
        "relevance": _strict_string_enum(["financial_signal", "possible_noise", "unknown"]),
        "signal_type": _strict_string_enum(["debit", "reversal", "failed_payment", "atm_failure", "invoice_overdue", "refund", "other", "unknown"]),
        "evidence_summary": {"type": "string"},
        "needs_review": {"type": "boolean"},
        "review_reasons": {"type": "array", "items": {"type": "string"}},
        "trust_tier": _strict_string_enum(["deterministic", "llm_suggestion", "user_confirmed"]),
        "model_version": {"type": "string"},
    },
    "required": ["message_id", "relevance", "signal_type", "evidence_summary", "needs_review", "review_reasons", "trust_tier", "model_version"],
}


def _field_schema(value_type: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "value": {"type": [value_type["type"], "null"]},
            "source_quote": {"type": ["string", "null"]},
            "status": _strict_string_enum(["present", "absent", "ambiguous"]),
        },
        "required": ["value", "source_quote", "status"],
    }


EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "message_id": {"type": "string"},
        "relevance": _strict_string_enum(["financial_signal", "possible_noise", "unknown"]),
        "signal_type": _strict_string_enum(["debit", "reversal", "failed_payment", "atm_failure", "invoice_overdue", "refund", "other", "unknown"]),
        "amount": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "value_paise": {"type": ["integer", "null"]},
                "source_quote": {"type": ["string", "null"]},
                "status": _strict_string_enum(["present", "absent", "ambiguous"]),
            },
            "required": ["value_paise", "source_quote", "status"],
        },
        "currency": _strict_string_enum(["INR", "unknown"]),
        "transaction_reference": _field_schema({"type": "string"}),
        "event_date": _field_schema({"type": "string"}),
        "reversal_date": _field_schema({"type": "string"}),
        "channel": _strict_string_enum(["UPI", "ATM", "CARD", "NACH", "MSME", "OTHER", "unknown"]),
        "counterparty": {"type": ["string", "null"]},
        "explicit_failure_language": {"type": "boolean"},
        "evidence_summary": {"type": "string"},
        "needs_review": {"type": "boolean"},
        "review_reasons": {"type": "array", "items": {"type": "string"}},
        "conflicts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "field": {"type": "string"},
                    "deterministic_value": {"type": ["string", "integer", "null"]},
                    "llm_value": {"type": ["string", "integer", "null"]},
                    "status": {"type": "string"},
                    "action": {"type": "string"},
                },
                "required": ["field", "deterministic_value", "llm_value", "status", "action"],
            },
        },
        "model_version": {"type": "string"},
        "trust_tier": _strict_string_enum(["deterministic", "llm_suggestion", "user_confirmed"]),
    },
    "required": [
        "message_id",
        "relevance",
        "signal_type",
        "amount",
        "currency",
        "transaction_reference",
        "event_date",
        "reversal_date",
        "channel",
        "counterparty",
        "explicit_failure_language",
        "evidence_summary",
        "needs_review",
        "review_reasons",
        "conflicts",
        "model_version",
        "trust_tier",
    ],
}


class GroqClient(LLMClient):
    """Server-side Groq adapter; it never logs prompts, responses, or API keys."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        triage_model: str | None = None,
        extract_model: str | None = None,
        recheck_model: str | None = None,
        base_url: str = GROQ_URL,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_completion_tokens: int = DEFAULT_MAX_COMPLETION_TOKENS,
        spend_cap_usd: float = 0.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("GROQ_API_KEY")
        self.models = {
            "triage": triage_model or os.getenv("LLM_MODEL_TRIAGE", "openai/gpt-oss-20b"),
            "extract": extract_model or os.getenv("LLM_MODEL_EXTRACT", "openai/gpt-oss-20b"),
            "recheck": recheck_model or os.getenv("LLM_MODEL_RECHECK", "openai/gpt-oss-20b"),
        }
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.max_completion_tokens = min(max_completion_tokens, 4096)
        self.budget = SpendBudget(spend_cap_usd)
        self._transport = transport
        self._sleep = sleep

    def triage(self, payload: MessagePayload) -> LLMResponse[TriageResult]:
        response = self._complete("triage", payload, TRIAGE_SCHEMA)
        if response.llm_status != LLMStatus.OK or response.result is None:
            return LLMResponse(response.llm_status, error=response.error)
        try:
            return LLMResponse(LLMStatus.OK, TriageResult.model_validate(response.result))
        except Exception as exc:
            return LLMResponse(LLMStatus.INVALID_OUTPUT, error=type(exc).__name__)

    def extract(self, payload: MessagePayload) -> LLMResponse[ExtractionResult]:
        response = self._complete("extract", payload, EXTRACTION_SCHEMA)
        if response.llm_status != LLMStatus.OK or response.result is None:
            return LLMResponse(response.llm_status, error=response.error)
        try:
            result = ExtractionResult.model_validate(response.result)
            validate_extraction(result, payload)
            return LLMResponse(LLMStatus.OK, result)
        except Exception as exc:
            return LLMResponse(LLMStatus.INVALID_OUTPUT, error=type(exc).__name__)

    def _complete(self, task: str, payload: MessagePayload, schema: dict[str, Any]) -> LLMResponse[dict[str, Any]]:
        if not self.api_key:
            return LLMResponse(LLMStatus.UNAVAILABLE, error="provider key is not configured")
        model = self.models[task]
        pricing = PRICING.get(model, GroqModelPricing(0.0, 0.0))
        try:
            self.budget.reserve_worst_case(
                input_tokens=max(1, len(payload.body_text + payload.subject + payload.snippet) // 4),
                output_tokens=self.max_completion_tokens,
                input_rate=pricing.input_per_million,
                output_rate=pricing.output_per_million,
            )
        except SpendCapExceeded:
            return LLMResponse(LLMStatus.UNAVAILABLE, error="spend cap exceeded before provider request")

        system = build_prompt("triage_v1" if task == "triage" else "extract_v1", "")
        request = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": "<EMAIL_DATA>\n" + payload.model_dump_json() + "\n</EMAIL_DATA>"},
            ],
            "temperature": 0,
            "max_completion_tokens": self.max_completion_tokens,
            "stream": False,
            "tool_choice": "none",
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": f"haq_{task}_v1", "strict": True, "schema": schema},
            },
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout_seconds, transport=self._transport) as client:
                    result = client.post(self.base_url, headers=headers, json=request)
                if result.status_code == 429 or result.status_code >= 500:
                    if attempt < self.max_retries:
                        self._sleep(0.25 * (2**attempt))
                        continue
                    return LLMResponse(LLMStatus.UNAVAILABLE, error=f"provider_http_{result.status_code}")
                if result.status_code >= 400:
                    return LLMResponse(LLMStatus.UNAVAILABLE, error=f"provider_http_{result.status_code}")
                data = result.json()
                usage = data.get("usage", {})
                self.budget.record(usage, pricing.input_per_million, pricing.output_per_million)
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                return LLMResponse(LLMStatus.OK, parsed)
            except httpx.TimeoutException:
                if attempt < self.max_retries:
                    self._sleep(0.25 * (2**attempt))
                    continue
                return LLMResponse(LLMStatus.TIMEOUT, error="provider_timeout")
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
                return LLMResponse(LLMStatus.INVALID_OUTPUT, error=type(exc).__name__)
        return LLMResponse(LLMStatus.UNAVAILABLE, error="provider_request_failed")


__all__ = ["EXTRACTION_SCHEMA", "GroqClient", "SpendBudget", "SpendCapExceeded", "TRIAGE_SCHEMA"]
