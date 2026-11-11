from __future__ import annotations

import unittest
from datetime import date
from engine.calculators.msme import msme_due_date, msme_interest


class TestMsmeCalculator(unittest.TestCase):
    def test_due_date_without_agreement_is_15_days(self) -> None:
        acceptance = date(2026, 9, 1)
        due = msme_due_date(acceptance, has_written_agreement=False)
        self.assertEqual(due, date(2026, 9, 16))

    def test_due_date_with_agreement_capped_at_45_days(self) -> None:
        acceptance = date(2026, 9, 1)
        # Even if 60 days agreed, cap at 45
        due = msme_due_date(acceptance, has_written_agreement=True, agreed_days=60)
        self.assertEqual(due, date(2026, 10, 16))

    def test_interest_compounding_calculation(self) -> None:
        principal = 10000000  # ₹1,00,000 in paise
        interest = msme_interest(principal, days_overdue=30, bank_rate_pct=6.5)
        # 19.5% per annum for 1 month is approx ₹1,625
        self.assertGreater(interest, 150000)
        self.assertLess(interest, 180000)

    def test_zero_days_overdue_is_zero_interest(self) -> None:
        principal = 10000000
        self.assertEqual(msme_interest(principal, days_overdue=0), 0)


if __name__ == "__main__":
    unittest.main()
