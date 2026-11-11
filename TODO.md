# T5 Frontend TODO

## Mobile-first golden path

- [x] Home shows three entry cards: payment failed, business owes me, forgotten money.
- [x] Upload/paste screen has file picker, paste area, bank selector, protected-PDF password field, privacy note, and no-storage statement.
- [x] Review screen shows editable cleaned transactions and highlights the low-confidence row.
- [x] Candidates screen asks confirmation questions before computation.
- [x] Result screen renders the deadline, range amount, unresolved convention, `UNVERIFIED RULE` stamp, trace, sources, conflicts, and next action.
- [x] Claim-pack screen renders an editable draft, evidence checklist, escalation ladder, copy, and print controls.

## Shared trust and accessibility

- [x] Disclaimer banner, privacy note, confidence badge, loading, empty, and error states exist.
- [x] In-memory state only; Clear my data wipes the session; reload starts clean.
- [x] Copy uses “the rule says” / “you could”, not legal conclusions.
- [x] Tap targets are at least 44px and controls have labels.
- [x] Mock-first API adapter preserves the documented `/v1/*` contract for later integration.
- [x] `manus-routes.json` is served for the SPA route.

## Verification

- [x] TypeScript production build passes.
- [x] Frontend lint/type checks pass through `npm run check`.
- [ ] Playwright smoke test against mock and real API (follow-up once browser test tooling is added to the repo).
