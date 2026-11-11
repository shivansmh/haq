from clean.normalize import normalize_row, parse_money
from clean.redact import redact_sensitive
from clean.validate import dedupe_transactions, running_balance_ok
from data.synthetic.generator import build_scenarios
from ingest.csv_reader import parse_csv
from ingest.paste_parser import parse_alert_text
from match.classify import classify
from match.pairing import pair_transactions


def test_money_redaction_and_normalization() -> None:
    assert parse_money("₹1,234.50") == 123450
    assert parse_money("0.005") == 1
    pan = "ABCDE" + "1234" + "F"
    reference = "123456" + "789012"
    assert "PAN REDACTED" in redact_sensitive(pan)
    tx = normalize_row(
        {"date": "03/11/2026", "narration": f"UPI ref {reference}", "debit": "2,000", "credit": ""},
        "fixture",
        2,
    )
    assert tx.debit_paise == 200000
    assert "ACCOUNT REDACTED" in tx.narration_clean or "ID REDACTED" in tx.narration_clean


def test_csv_ingest_classify_and_pair_reversed() -> None:
    reference = "123456" + "789012"
    text = (
        "Date,Narration,Debit,Credit,Balance,Reference\n"
        f"03/11/2026,UPI payment,2000,,8000,{reference}\n"
        f"04/11/2026,UPI reversal,,2000,10000,{reference}\n"
    )
    transactions = [classify(item) for item in parse_csv(text)]
    assert transactions[0].channel == "UPI"
    assert pair_transactions(transactions) == []


def test_unreversed_debit_is_a_candidate_not_a_claim() -> None:
    text = "Date,Narration,Debit,Credit,Balance,Reference\n03/11/2026,ATM cash withdrawal,5000,,,\n"
    transactions = [classify(item) for item in parse_csv(text)]
    candidates = pair_transactions(transactions)
    assert len(candidates) == 1
    assert candidates[0].match.label == "unreversed"
    assert candidates[0].requires_confirmation is True


def test_paste_parser_keeps_unparsed_text_visible() -> None:
    parsed, warnings = parse_alert_text("03/11/2026 UPI payment debited ₹2,000 RRN 123456")
    assert len(parsed) == 1
    assert parsed[0].debit_paise == 200000
    assert parse_alert_text("unknown alert text")[1]


def test_running_balance_and_deduplication() -> None:
    first = normalize_row(
        {"date": "03/11/2026", "narration": "UPI payment", "debit": "2,000", "balance": "8,000"},
        "fixture",
        2,
    )
    second = normalize_row(
        {"date": "04/11/2026", "narration": "UPI reversal", "credit": "2,000", "balance": "10,000"},
        "fixture",
        3,
    )
    assert running_balance_ok([first, second]) is True
    assert len(dedupe_transactions([first, first, second])) == 2


def test_synthetic_expected_candidate_counts() -> None:
    for scenario in build_scenarios():
        transactions = [classify(item) for item in parse_csv(scenario.csv_text, scenario.name)]
        assert len(pair_transactions(transactions)) == scenario.expected_candidate_count
