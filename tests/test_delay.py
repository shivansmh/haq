from __future__ import annotations

import unittest
from datetime import date

from engine.delay import compute_range, delay_days


class TestDelayModule(unittest.TestCase):
    def test_appendix_a_golden_example(self) -> None:
        # Appendix A: UPI debit on 3 Nov, deadline 4 Nov, reversal on 9 Nov
        deadline = date(2026, 11, 4)
        resolved = date(2026, 11, 9)
        self.assertEqual(compute_range(deadline, resolved, 10000), (40000, 50000))

    def test_resolved_on_deadline_is_zero(self) -> None:
        d = date(2026, 11, 4)
        self.assertEqual(compute_range(d, d, 10000), (0, 0))

    def test_resolved_before_deadline_is_zero(self) -> None:
        deadline = date(2026, 11, 4)
        resolved = date(2026, 11, 3)
        self.assertEqual(delay_days(deadline, resolved, count_resolution_day=True), 0)


if __name__ == "__main__":
    unittest.main()
