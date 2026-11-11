# T2 accuracy set

The committed T2 test set is synthetic because it uses four invented layouts rather than real bank statements. The supplied corpus contains 20 PDFs and 640 labelled debit rows. Its generator and line-by-line explanation live in `data/synthetic/generate_synthetic.py` and `data/synthetic/SYNTHETIC_DATA_EXPLAINED.md`; the checked-in results are summarized in [`data/synthetic/accuracy_report.json`](../data/synthetic/accuracy_report.json).

The revised metrics are pairing accuracy and true-failure candidate coverage, not failed-payment precision. On this corpus, pairing accuracy is 100% and true-failure candidate coverage is 80% (80/100). On-time reversals are intentionally not shown as candidates; late and never-reversed cases are surfaced.

## Required research/data input

Before claiming the T2 targets on real data, add five genuinely redacted statements from each target bank, plus `expected_candidates.csv` labels. Keep them outside `data/real/` until the privacy review is complete; add only approved redacted fixtures under `data/redacted/`.

The current implementation does not claim the suggested 98% row parsing, 95% balance-chain, 90% recall or 85% precision targets on real statements.
