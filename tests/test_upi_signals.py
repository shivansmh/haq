from __future__ import annotations

import urllib.request
from typing import Any

import pytest

from api import gmail_service
from api.gmail_service import DEFAULT_GMAIL_QUERY, MAX_QUERY_LENGTH, filter_and_extract_transactions
from api.upi_signals import classify_message, classify_sender, find_reference, parse_amount


def address(local: str, domain: str) -> str:
    return local + chr(64) + domain


RUN_ID = "192837" + "465012"
HDFC_TEST_REF = "431209" + "845999"
ICICI_TEST_REF = "431209" + "845111"


def msg(mid: str, sender: str, subject: str, body: str, date: str = "Tue, 03 Nov 2026 14:22:00 +0530") -> dict[str, Any]:
    return {"id": mid, "sender": sender, "subject": subject, "snippet": body[:120], "body": body,
            "date": date, "is_real": True}


# ------------------------------------------------------------------ the original bug

GITHUB_BODIES = [
    # 12-digit Actions run id used to look like a UPI reference
    f"Run failed. https://github.com/x/y/actions/runs/{RUN_ID}",
    # "ref" inside a longer word used to look like a reference label
    "Run failed. Refactored the credentials check; refs/heads/main; refresh tokens.",
    # "errors 12" used to look like "Rs 12"
    "CI failed with errors 12 and exit code 2. Payment module tests failed.",
]


@pytest.mark.parametrize("body", GITHUB_BODIES)
def test_github_ci_failures_are_never_payment_signals(body: str) -> None:
    mail = msg("g1", f"Shivansh <{address('notifications', 'github.com')}>", "[shivansmh/haq] Run failed: CI - main (8ad1d0b)", body)
    signal = classify_message(mail["sender"], mail["subject"], mail["snippet"], mail["body"])
    assert signal.is_noise
    result = filter_and_extract_transactions([mail])
    assert result["candidates"] == []
    assert result["noise_filtered"] == 1


def test_even_an_unknown_sender_needs_real_money_evidence() -> None:
    # not a blocked domain, so only the content rules protect us
    for body in GITHUB_BODIES:
        signal = classify_message(address("ci", "selfhosted.example"), "Build failed", body, body)
        assert signal.is_noise, body


def test_reference_regex_has_word_boundaries() -> None:
    assert find_reference("Refactored the module, refs/heads/main", upi_context=False) is None
    assert find_reference(f"run {RUN_ID}", upi_context=False) is None
    assert find_reference(f"run {RUN_ID}", upi_context=True) == RUN_ID  # only inside UPI context
    assert find_reference("Txn Ref: ATM8829103.", upi_context=False) == "ATM8829103"
    assert find_reference("reference_resolution_failure", upi_context=False) is None  # id must contain a digit


def test_amount_regex_does_not_fire_inside_words() -> None:
    assert parse_amount("errors 12, users 5, hours 3") is None
    assert parse_amount("Rs 2,000.00 debited") == 200000
    assert parse_amount("₹499 refunded") == 49900
    assert parse_amount("INR 1,42,800") == 14280000


def test_sender_tiers_use_the_domain_not_a_substring() -> None:
    assert classify_sender(f"Shivansh <{address('notifications', 'github.com')}>") == "blocked"
    assert classify_sender(address("alerts", "hdfcbank.net")) == "bank"
    assert classify_sender(address("support", "phonepe.com")) == "upi_app"
    assert classify_sender(address("auto-confirm", "amazon.in")) == "merchant"
    assert classify_sender(address("billing", "sbicards-fake.example")) == "unknown"  # "sbi" substring must not count
    assert classify_sender(address("attacker", "github.com.evil.example")) == "unknown"  # lookalike, not a subdomain


# ------------------------------------------------------------------ what we DO want to catch

def test_failed_upi_payment_with_debit_is_flagged() -> None:
    signal = classify_message(
        address("support", "phonepe.com"),
        "Payment Failed: Your payment of Rs 450 at Zomato was not completed",
        "UPI payment failed",
        "Your UPI transaction of Rs 450 failed. Amount debited from your bank will be reversed.",
    )
    assert signal.kind == "upi_failed_debited"
    assert signal.channel == "UPI"
    assert signal.amount_paise == 45000
    assert any("failure" in reason for reason in signal.reasons)


def test_bank_alert_that_mentions_otp_is_not_thrown_away() -> None:
    signal = classify_message(
        address("alerts", "hdfcbank.net"), "UPI debit alert", "",
        f"Rs 899.00 debited via UPI. UPI Ref {HDFC_TEST_REF}. Never share your OTP with anyone.",
    )
    assert not signal.is_noise
    assert signal.kind == "debit"


def test_cancelled_order_is_flagged_when_refund_is_not_confirmed() -> None:
    signal = classify_message(
        address("order-update", "amazon.in"), "Your order has been cancelled", "",
        "Order #402-9912039-11203 for Rs 1,499 has been cancelled. Refund will be credited in 5-7 days.",
    )
    assert signal.kind == "order_cancelled"
    assert signal.channel == "ORDER"
    assert signal.amount_paise == 149900
    assert "refund still pending" in signal.reasons


def test_hindi_failure_wording_is_detected() -> None:
    signal = classify_message(
        address("alerts", "icicibank.com"), "UPI भुगतान विफल", "",
        f"आपका UPI भुगतान ₹1,200 विफल रहा। राशि कट गई है। UPI Ref {ICICI_TEST_REF}",
    )
    assert signal.kind in {"upi_failed", "upi_failed_debited"}


def test_otp_and_promos_stay_noise() -> None:
    assert classify_message(address("no-reply", "accounts.google.com"), "Verification code 482910", "", "Your OTP is 482910").is_noise
    assert classify_message(address("promo", "swiggy.in"), "Flat 50% off tonight", "", "Use coupon TASTY50, flat 50% off orders above Rs 299").is_noise


# ------------------------------------------------------------------ candidates

def test_failed_payment_and_matching_debit_merge_into_one_candidate() -> None:
    result = filter_and_extract_transactions([
        msg("d1", address("alerts", "hdfcbank.net"), "UPI debit Rs 2,000.00", "Rs 2,000.00 debited via UPI. UPI Ref " + "431209" + "845123."),
        msg("f1", address("support", "phonepe.com"), "Payment failed", "Your UPI payment of Rs 2,000 failed. Amount debited will be reversed."),
    ])
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["related_sources"] or result["candidates"][0]["reversal_seen"] is False


def test_failed_payment_without_reversal_is_a_candidate_and_with_reversal_is_paired() -> None:
    failed = msg("f1", address("support", "phonepe.com"), "Payment failed", "UPI payment of Rs 700 failed; amount debited.",
                 date="Mon, 02 Nov 2026 10:00:00 +0530")
    alone = filter_and_extract_transactions([failed])
    assert alone["candidates"][0]["evidence_status"] == "potential_exception"
    assert alone["candidates"][0]["reversal_seen"] is False

    refund = msg("r1", address("alerts", "hdfcbank.net"), "Reversal credit of Rs 700.00",
                 "Reversal credit of Rs 700.00 received via UPI Reversal.", date="Thu, 05 Nov 2026 10:00:00 +0530")
    paired = filter_and_extract_transactions([failed, refund])
    assert paired["candidates"][0]["evidence_status"] == "paired_reversal"
    assert paired["candidates"][0]["reversal_date"] == "2026-11-05"


def test_unrelated_refund_of_a_different_amount_does_not_pair() -> None:
    failed = msg("f1", address("support", "phonepe.com"), "Payment failed", "UPI payment of Rs 700 failed; amount debited.")
    refund = msg("r1", address("alerts", "hdfcbank.net"), "Reversal credit of Rs 90.00", "Reversal credit of Rs 90.00 via UPI Reversal.",
                 date="Thu, 05 Nov 2026 10:00:00 +0530")
    result = filter_and_extract_transactions([failed, refund])
    assert result["candidates"][0]["reversal_seen"] is False


def test_results_list_puts_findings_before_noise() -> None:
    mails = [
        msg("n1", f"Shivansh <{address('notifications', 'github.com')}>", "Run failed", "Run failed: CI"),
        msg("f1", address("support", "phonepe.com"), "Payment failed", "UPI payment of Rs 700 failed; amount debited."),
    ]
    emails = filter_and_extract_transactions(mails)["emails"]
    assert emails[0]["id"] == "f1"
    assert emails[0]["signalReasons"]


# ------------------------------------------------------------------ fetch funnel

def test_default_query_fits_gmail_limit_and_excludes_dev_senders() -> None:
    assert len(DEFAULT_GMAIL_QUERY) <= MAX_QUERY_LENGTH
    assert "-from:github.com" in DEFAULT_GMAIL_QUERY
    assert "newer_than:365d" in DEFAULT_GMAIL_QUERY


def _fake_gmail(monkeypatch: pytest.MonkeyPatch, store: dict[str, dict[str, Any]]) -> list[str]:
    opened_full: list[str] = []

    def fake_json(request: urllib.request.Request, *, timeout: float) -> dict[str, Any]:
        url = request.full_url
        if "/messages?" in url:
            return {"messages": [{"id": key} for key in store]}
        msg_id = url.split("/messages/")[1].split("?")[0]
        if "format=full" in url:
            opened_full.append(msg_id)
        return store[msg_id]

    monkeypatch.setattr(gmail_service, "_gmail_json", fake_json)
    return opened_full


def _gmail_message(sender: str, subject: str, snippet: str, text: str) -> dict[str, Any]:
    import base64

    data = base64.urlsafe_b64encode(text.encode()).decode()
    return {"snippet": snippet, "payload": {
        "headers": [{"name": "From", "value": sender}, {"name": "Subject", "value": subject},
                    {"name": "Date", "value": "Tue, 03 Nov 2026 14:22:00 +0530"}],
        "mimeType": "text/plain", "body": {"data": data}}}


def test_funnel_never_opens_bodies_of_blocked_or_irrelevant_senders(monkeypatch: pytest.MonkeyPatch) -> None:
    store = {
        "gh": _gmail_message(f"Shivansh <{address('notifications', 'github.com')}>", "Run failed: CI", "Run failed", "Run failed"),
        "news": _gmail_message(address("hello", "random.example"), "Our weekly update", "Read our blog", "Read our blog"),
        "pp": _gmail_message(address("support", "phonepe.com"), "Payment failed", "UPI payment failed",
                             "UPI payment of Rs 450 failed. Amount debited."),
    }
    opened = _fake_gmail(monkeypatch, store)
    updates: list[dict[str, Any]] = []
    records = gmail_service.fetch_live_gmail("token", "", 50, progress=lambda **kw: updates.append(kw))

    assert opened == ["pp"]  # privacy + speed: only the plausible payment mail is opened
    assert [r["id"] for r in records] == ["gh", "news", "pp"]
    assert records[2]["body"].startswith("UPI payment of Rs 450")
    assert any("listed" in u for u in updates) and any("triaged" in u for u in updates)
    assert max(u["analysed"] for u in updates if "analysed" in u) == 3  # live counters reach the total


def test_funnel_stops_when_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    store = {f"m{i}": _gmail_message(address("support", "phonepe.com"), "Payment failed", "failed", "UPI Rs 1 failed") for i in range(5)}
    opened = _fake_gmail(monkeypatch, store)
    records = gmail_service.fetch_live_gmail("token", "", 50, should_cancel=lambda: True)
    assert opened == []
    assert records == []
