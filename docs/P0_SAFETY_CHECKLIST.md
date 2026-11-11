# P0 safety checklist

This checklist is the deterministic gate before adding an LLM to Haq.

## Completed

- Gmail counts are derived from the bounded result set; no synthetic offsets are added.
- Live Gmail search uses a bounded query, a 100-message cap, pagination, a 500-character query limit, and Gmail-supported search syntax.
- Multipart bodies are inspected transiently across readable parts, capped at 8,000 characters, and never returned or persisted.
- A bank debit is a financial signal, not automatically a violation.
- Candidates are created only from explicit exception language or a matching debit/reversal pair with evidence-derived dates, amounts, and references.
- Pasted text that cannot be parsed returns `unparseable` with zero transactions; synthetic data is only available through the explicit demo endpoint.
- Selected frontend findings provide the dates, amount, channel, and reference to compute and draft endpoints.
- Live compute and draft failures are surfaced to the user; no silent mock fallback remains.
- Seeded or unresolved registry entries return `UNVERIFIED RULE`, `Low` confidence, and an illustrative flag.
- Classifier summaries use routing/evidence language rather than asserting that a legal entitlement exists.
- Gmail sessions have a one-hour absolute/idle lifetime.
- Google token revocation uses a POST body, not a token-bearing URL.
- Ruff, backend tests, compile checks, TypeScript, and production build are required gates.

## Deliberate boundary

The LLM layer must not decide whether a legal right exists, calculate compensation, invent dates or amounts, or upgrade confidence. If introduced later, it may assist with bounded noise classification or extraction only when the deterministic evidence fields and uncertainty status remain authoritative and the raw model output is never shown as a legal conclusion.
