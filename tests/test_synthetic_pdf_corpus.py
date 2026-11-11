import csv
from collections import defaultdict
from pathlib import Path

from ingest.pdf_reader import parse_pdf, scan_pdf
from match.pairing import pair_all, pair_transactions

ROOT = Path("data/synthetic")


def _labels() -> dict[str, dict[int, dict[str, str]]]:
    result: dict[str, dict[int, dict[str, str]]] = defaultdict(dict)
    with (ROOT / "expected_candidates.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            result[row["statement_id"]][int(row["row_number"])] = row
    return result


def test_supplied_synthetic_corpus_and_revised_metrics() -> None:
    labels = _labels()
    pairing_correct = 0
    total_rows = 0
    true_failures = 0
    surfaced_failures = 0
    manifest = list(csv.DictReader((ROOT / "MANIFEST.csv").open(encoding="utf-8")))
    assert len(manifest) == 20

    for item in manifest:
        statement_id = item["statement_id"]
        layout = item["layout_name"].removeprefix("synthetic_")
        path = ROOT / layout / f"{layout}_{statement_id[-2:]}.pdf"
        parsed = parse_pdf(path)
        assert scan_pdf(path) == []
        assert parsed.report.running_balance_ok is True
        assert len([row for row in parsed.transactions if row.debit_paise > 0]) == 32

        all_matches = {
            candidate.transaction.source_row: candidate
            for candidate in pair_all(parsed.transactions)
        }
        surfaced = {
            candidate.transaction.source_row for candidate in pair_transactions(parsed.transactions)
        }
        for row_number, expected in labels[statement_id].items():
            total_rows += 1
            pairing_correct += all_matches[row_number].match.label == expected["expected_label"]
            if expected["is_true_failure"] == "yes":
                true_failures += 1
                surfaced_failures += row_number in surfaced

    assert total_rows == 640
    assert pairing_correct / total_rows == 1.0
    assert surfaced_failures / true_failures == 0.8
