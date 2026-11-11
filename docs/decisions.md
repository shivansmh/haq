# Technical decisions

## 2026-11-11 — T0 foundation

- **Money representation:** future engine code will use integer paise, never floating-point rupees.
- **Date representation:** future engine code will use date-only ISO values without time zones.
- **Holiday scope:** unresolved in research; no holiday calendar or default scope is implemented until the registry and decision owner settle it.
- **Runtime mode:** API defaults to `demo`; Seeded rules must be visibly stamped `UNVERIFIED RULE`.
- **Privacy:** T0 has no persistence and no raw request-body logging.
- **Branching:** work for this task is committed directly to `main` as requested; future phase work should use reviewed feature branches if branch protection is enabled.

Open decisions are not silently resolved. Each convention must cite its source and date when decided.

## 2026-11-11 — T2 initial data layer

- **Initial scope:** deterministic CSV and pasted-alert ingestion; PDF and bank-specific adapters remain next steps.
- **Money:** normalized to integer paise; no floating-point amounts enter pairing.
- **Candidate semantics:** an unreversed or ambiguous debit is only a suggestion; user confirmation is required before computation.
- **Accuracy targets:** the plan's 98% parse, 95% balance-chain, 90% recall and 85% precision targets are not claimed until five genuinely redacted statements per target bank are available.
- **Needed research material:** redacted statements and expected candidate labels, with bank names and layout metadata but no identifiers.
