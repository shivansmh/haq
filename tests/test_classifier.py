from __future__ import annotations

import unittest
from engine.classifier import classify_prompt, extract_entities


class TestClassifier(unittest.TestCase):
    def test_classify_failed_upi_payment(self) -> None:
        res = classify_prompt("Swiggy debited ₹2,000 via UPI 5 days ago and the transaction failed")
        self.assertEqual(res["category"], "failed_payment")
        self.assertGreaterEqual(res["confidence"], 0.70)
        self.assertEqual(res["extracted_entities"]["amount_inr"], 2000)
        self.assertEqual(res["extracted_entities"]["counterparty"], "SWIGGY")

    def test_classify_msme_invoice(self) -> None:
        res = classify_prompt("My client has not paid my invoice of 1.5 lakh for 2 months under MSME")
        self.assertEqual(res["category"], "msme_dues")
        self.assertEqual(res["extracted_entities"]["amount_inr"], 150000)
        self.assertIn("MSMED Act", res["statutory_law"])

    def test_classify_unclaimed_assets(self) -> None:
        res = classify_prompt("How can I trace my grandfather's unclaimed shares and dormant bank account on UDGAM?")
        self.assertEqual(res["category"], "unclaimed_wealth")
        self.assertIn("UDGAM", res["statutory_law"])

    def test_extract_money_scales(self) -> None:
        ent = extract_entities("Pending amount is Rs. 50,000 and another bill of 2.5 lakh")
        self.assertEqual(ent["amount_inr"], 250000)


if __name__ == "__main__":
    unittest.main()
