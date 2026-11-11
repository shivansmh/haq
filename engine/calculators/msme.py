"""Haq Engine: MSME Delayed Dues and Statutory Interest Calculator (R-007, R-008, R-010).

Implements Section 15 & 16 of the Micro, Small and Medium Enterprises
Development (MSMED) Act, 2006:
- Section 15: Maximum payment window is 15 days (without agreement) or agreed period up to 45 days.
- Section 16: Compound interest with monthly rests at 3 times the RBI Bank Rate.
- Income-tax Act Section 43B(h) / Section 37(2)(g): Expense deduction disallowance.
"""

from __future__ import annotations

from datetime import date, timedelta


def msme_due_date(acceptance_date: date, has_written_agreement: bool, agreed_days: int = 45) -> date:
    """Compute statutory payment deadline under Section 15."""
    allowed_days = min(agreed_days, 45) if has_written_agreement else 15
    return acceptance_date + timedelta(days=allowed_days)


def msme_interest(
    amount_paise: int,
    days_overdue: int,
    bank_rate_pct: float = 6.5,
) -> int:
    """Calculate statutory interest in integer paise under Section 16.

    Statutory rate is 3x RBI Bank Rate with monthly rests.
    """
    if days_overdue <= 0:
        return 0

    annual_statutory_rate = (bank_rate_pct * 3.0) / 100.0
    monthly_rate = annual_statutory_rate / 12.0
    months = days_overdue / 30.417

    compounded = amount_paise * ((1.0 + monthly_rate) ** months)
    interest_paise = round(compounded - amount_paise)
    return max(0, interest_paise)
