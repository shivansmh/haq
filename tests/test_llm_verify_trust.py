from __future__ import annotations

from datetime import date

import pytest

from llm.trust import (
    FieldTrustTier,
    TrustedValue,
    UntrustedForCalculationError,
    assign_tier,
    report_conflicts,
    value_for_calculation,
)
from llm.verify import (
    AmbiguousDateError,
    QuoteVerificationError,
    normalise_date,
    normalise_indian_digit_grouping,
    verify_quote,
)


def test_real_looking_quote_cannot_prove_a_fabricated_amount() -> None:
    with pytest.raises(QuoteVerificationError, match="extracted value"):
        verify_quote(
            "Payment alert: Rs 2,000 debited.",
            "Payment alert: Rs 2,000 debited.",
            300000,
            kind="amount",
        )


def test_quote_must_be_present_in_original_message() -> None:
    with pytest.raises(QuoteVerificationError, match="not present"):
        verify_quote("Payment alert: Rs 2,000 debited.", "Rs 9,000 debited", 900000, kind="amount")


def test_value_must_appear_inside_a_quote_that_is_present() -> None:
    with pytest.raises(QuoteVerificationError, match="inside"):
        verify_quote(
            "Payment alert: Rs 2,000 debited. Ref ABC-123.",
            "Payment alert: Rs 2,000 debited.",
            "ABC-123",
            kind="reference",
        )


def test_indian_grouping_and_currency_variants_are_normalised() -> None:
    assert normalise_indian_digit_grouping("₹1,23,456") == "₹123456"
    assert verify_quote(
        "Debit of INR 1,23,456.00 was recorded.",
        "₹ 123456.00",
        12345600,
        kind="amount",
    )


def test_ambiguous_numeric_date_is_rejected_without_sender_convention() -> None:
    with pytest.raises(AmbiguousDateError):
        normalise_date("03/04/2026")
    assert normalise_date("03/04/2026", sender_convention="DMY") == date(2026, 4, 3)
    assert normalise_date("03/04/2026", sender_convention="MDY") == date(2026, 3, 4)


def test_textual_bank_alert_date_is_quote_verifiable() -> None:
    assert verify_quote(
        "UPI payment debited on 03-Nov-2026.",
        "debited on 03-Nov-2026",
        date(2026, 11, 3),
        kind="date",
    )
    assert verify_quote(
        "Payment received on Nov 3, 2026.",
        "received on Nov 3, 2026",
        date(2026, 11, 3),
        kind="date",
    )


def test_conflicts_are_reported_and_never_resolved_silently() -> None:
    conflicts = report_conflicts(
        {"amount_paise": 200000, "event_date": date(2026, 4, 3)},
        {"amount_paise": 250000, "event_date": date(2026, 4, 3)},
    )
    assert conflicts == [
        {
            "field": "amount_paise",
            "deterministic_value": 200000,
            "llm_value": 250000,
            "status": "conflict",
            "action": "ask_user",
        }
    ]


def test_tiers_are_explicit_and_t_b_cannot_feed_calculations() -> None:
    assert assign_tier(source="deterministic") == FieldTrustTier.T_A
    assert assign_tier(source="ai", verified_in_text=True) == FieldTrustTier.T_B
    assert assign_tier(source="ai", verified_in_text=True, user_confirmed=True) == FieldTrustTier.T_C
    with pytest.raises(UntrustedForCalculationError, match="T-B"):
        value_for_calculation(TrustedValue(200000, FieldTrustTier.T_B, "amount_paise"))
    assert value_for_calculation(TrustedValue(200000, FieldTrustTier.T_A, "amount_paise")) == 200000
    assert value_for_calculation(TrustedValue(200000, FieldTrustTier.T_C, "amount_paise")) == 200000


def test_unverified_ai_value_cannot_be_assigned_a_trust_tier() -> None:
    with pytest.raises(ValueError, match="verified"):
        assign_tier(source="ai", verified_in_text=False)
