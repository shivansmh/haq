# a4-prompts-fixtures walkthrough

## Counts and files

A4 adds versioned prompt files in `llm/prompts/`: `triage_v1.txt`, `extract_v1.txt`, and a category-driven `builder.py` backed by `categories.json`. Both prompts state that email is data rather than instructions, require short source quotes, answer unknown when unsure, forbid legal or amount decisions, use `<EMAIL_DATA>` delimiters, and provide no tools or network access.

The generator is `scripts/generate_synthetic_emails.py`. With seed `20261112`, it produces 155 fixtures: 20 bank debits, 15 reversals/refunds, 10 failed payments, 10 ATM failures, 10 overdue notices, 20 look-alike promotions/OTP/shipping/social/newsletter messages, 20 ambiguous/adversarial cases, 10 missing-field cases, and 40 injection/adversarial cases. Every fixture has plain-text and HTML forms plus a JSON label.

The split is 70 dev, 45 held-out, and 40 unseen. Unseen fixtures use separate `*-template-unseen` identifiers. The prompt example template set is empty because the prompts intentionally contain no fixture examples; therefore no prompt example can leak into unseen.

## Tricky cases

An ambiguous date such as `03/04/26` is labelled ambiguous rather than silently interpreted. A current event followed by an older quoted message records the current event only and adds a review reason. A promotion listing a rupee amount, or a forged message claiming compensation, does not become a debit or legal entitlement; it remains look-alike or adversarial content requiring review.

## Validation

`tests/test_a4_prompts_fixtures.py` checks prompt safety wording, label structure, deterministic generation, category and split counts, unseen-template isolation, synthetic markers, and the repository’s sensitive-data scanner. No provider is called.
