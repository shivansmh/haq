from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any, Mapping


class FieldTrustTier(str, Enum):
    T_A = "T-A"  # deterministic parser output
    T_B = "T-B"  # AI suggestion verified against supplied text
    T_C = "T-C"  # explicitly confirmed by the user


class UntrustedForCalculationError(ValueError):
    """Raised when an AI-only value is presented as a calculation input."""


@dataclass(frozen=True, slots=True)
class TrustedValue:
    value: Any
    tier: FieldTrustTier
    field: str


def assign_tier(*, source: str, verified_in_text: bool = False, user_confirmed: bool = False) -> FieldTrustTier:
    """Assign the least-privileged tier; confirmation takes precedence over provenance."""
    if user_confirmed:
        return FieldTrustTier.T_C
    if source == "deterministic":
        return FieldTrustTier.T_A
    if source == "ai" and verified_in_text:
        return FieldTrustTier.T_B
    raise ValueError("an AI value must be verified in supplied text, or a known deterministic source is required")


def _json_value(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    return value


def _equivalent(left: Any, right: Any) -> bool:
    return _json_value(left) == _json_value(right)


def report_conflicts(
    deterministic: Mapping[str, Any],
    model: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Report disagreements without selecting either side as the winner."""
    conflicts: list[dict[str, Any]] = []
    for field in sorted(set(deterministic) & set(model)):
        deterministic_value = deterministic[field]
        model_value = model[field]
        if deterministic_value is None or model_value is None or _equivalent(deterministic_value, model_value):
            continue
        conflicts.append(
            {
                "field": field,
                "deterministic_value": _json_value(deterministic_value),
                "llm_value": _json_value(model_value),
                "status": "conflict",
                "action": "ask_user",
            }
        )
    return conflicts


def value_for_calculation(trusted: TrustedValue) -> Any:
    """Return only deterministic or user-confirmed values for downstream calculations."""
    if trusted.tier == FieldTrustTier.T_B:
        raise UntrustedForCalculationError(
            f"{trusted.field} is T-B AI-suggested evidence and cannot feed calculations"
        )
    if trusted.tier not in {FieldTrustTier.T_A, FieldTrustTier.T_C}:
        raise UntrustedForCalculationError(f"{trusted.field} has no calculation-safe trust tier")
    return trusted.value


__all__ = [
    "FieldTrustTier",
    "TrustedValue",
    "UntrustedForCalculationError",
    "assign_tier",
    "report_conflicts",
    "value_for_calculation",
]
