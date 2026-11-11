# T2 accuracy set

The committed T2 test set is synthetic because no redacted bank statements were available in this phase. Synthetic expected outcomes are encoded in `data/synthetic/generator.py`, checked in tests, and summarized in [`data/synthetic/accuracy_report.json`](../data/synthetic/accuracy_report.json).

## Required research/data input

Before claiming the T2 targets on real data, add five genuinely redacted statements from each target bank, plus `expected_candidates.csv` labels. Keep them outside `data/real/` until the privacy review is complete; add only approved redacted fixtures under `data/redacted/`.

The current implementation does not claim the suggested 98% row parsing, 95% balance-chain, 90% recall or 85% precision targets on real statements.
