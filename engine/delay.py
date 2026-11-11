"""Haq Engine: Delay and Turnaround Time Calculator (R-001 to R-006).

Implements the delay and statutory compensation logic under the RBI
Harmonised Turnaround Time (TAT) framework:
Circular DPSS.CO.PD No.629/02.01.014/2019-20.
All monetary amounts are represented as integer paise.
"""

from __future__ import annotations

from datetime import date


def delay_days(deadline: date, resolved_on: date, count_resolution_day: bool) -> int:
    """Compute days of delay past the mandated statutory turnaround deadline.

    If count_resolution_day is True (upper bound of Conflict C5), the day of
    reversal is included. If False (lower bound), it is excluded.
    """
    gap = (resolved_on - deadline).days
    if gap <= 0:
        return 0
    if count_resolution_day:
        return gap
    return gap - 1


def amount_owed(days: int, per_day_paise: int = 10000, cap_paise: int | None = None) -> int:
    """Calculate statutory compensation in integer paise.

    Default rate is ₹100 per day (10,000 paise).
    """
    total = days * per_day_paise
    if cap_paise is None:
        return total
    return min(total, cap_paise)


def compute_range(
    deadline: date,
    resolved_on: date,
    per_day_paise: int = 10000,
    cap_paise: int | None = None,
    count_resolution_day: bool | None = None,
) -> tuple[int, int]:
    """Return low and high statutory compensation in paise.

    Surfaces Research Conflict C5 when count_resolution_day is None.
    """
    options = [True, False] if count_resolution_day is None else [count_resolution_day]
    amounts = [
        amount_owed(delay_days(deadline, resolved_on, flag), per_day_paise, cap_paise)
        for flag in options
    ]
    return min(amounts), max(amounts)
