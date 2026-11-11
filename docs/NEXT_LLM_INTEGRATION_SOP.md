# Haq Next-Agent SOP: Safe LLM API Integration

**Status:** Ready for the next implementation agent  
**Scope:** Gmail noise cleaning, evidence extraction, and review assistance only  
**Out of scope:** Legal conclusions, rule selection, compensation calculation, claim submission, or confidence upgrades

## 1. Objective

Add an LLM-assisted processing layer to Haq’s Gmail sweep so the product can reduce email noise and normalize messy financial alerts into structured evidence. The LLM may identify whether a message is relevant, extract candidate facts, summarize the evidence, and explain uncertainty. It must not decide that a legal right exists, calculate compensation, choose a statutory rule, or convert missing evidence into a guessed value.

The existing deterministic pipeline remains authoritative:

```text
Gmail OAuth
  → bounded Gmail fetch
  → deterministic privacy/noise prefilter
  → LLM extraction/classification
  → deterministic validation and provenance checks
  → candidate review
  → registry-gated computation
  → user-edited draft
```

The next agent must preserve this order. Do not send the entire inbox directly to an LLM.

## 2. Current repository and deployment context

Repository: `https://github.com/shivansmh/haq/`

Frontend: GitHub Pages at `https://shivansmh.github.io/haq/`  
Backend: Render at `https://haq-api-u3pz.onrender.com`

Relevant code:

- Gmail service: `api/gmail_service.py`
- API routes: `api/main.py`
- API contracts: `api/schemas.py`
- Rights registry: `registry/R-*.yaml`
- Frontend API adapter: `web/src/api.ts`
- Frontend flow: `web/src/App.tsx`
- P0 safety tests: `tests/test_p0_safety.py`
- Safety boundary: `docs/P0_SAFETY_CHECKLIST.md`

Before editing, read the technical SOP, research SOP, P0 checklist, Gmail service, API schemas, and current tests. Do not assume the current registry entries are verified. `R-001` is currently Seeded, so live computation must remain blocked.

## 3. Non-negotiable safety rules

### 3.1 The LLM is not the legal engine

The model must never output or imply:

- “the user is entitled to compensation”;
- “the bank must pay”;
- “this is a violation” as a final conclusion;
- a statutory amount calculated from its own reasoning;
- a rule ID selected without deterministic routing;
- a confidence level higher than the registry and evidence allow;
- a date, amount, merchant, reference, or reversal event that is not present in the supplied evidence.

Preferred wording is evidence language: “message appears relevant,” “possible reversal signal,” “date not found,” “amount extracted from message text,” “needs user confirmation,” and “rule applicability remains unverified.”

### 3.2 No raw token or inbox dump enters the model

The LLM service must receive only the bounded messages selected by the deterministic prefilter. Never send OAuth tokens, refresh tokens, cookies, complete mailbox exports, attachments, unrelated personal messages, or hidden server configuration.

Only send the minimum fields needed for classification and extraction:

```json
{
  "message_id": "opaque-internal-id",
  "sender": "redacted-or-normalized-sender",
  "subject": "message subject",
  "snippet": "bounded snippet",
  "body_text": "bounded plain text",
  "received_at": "header-derived timestamp if available"
}
```

Use a strict per-message character cap. Start with 8,000 characters after deterministic truncation. Do not include the entire raw message in API responses or logs.

### 3.3 Deterministic values win

If the deterministic parser extracts a valid date, amount, reference, or sender, the LLM may suggest an alternative but may not silently overwrite it. Conflicts must be represented explicitly:

```json
{
  "field": "amount_paise",
  "deterministic_value": 200000,
  "llm_value": 250000,
  "status": "conflict",
  "action": "ask_user"
}
```

The downstream candidate may use only a value that passes deterministic validation or is explicitly confirmed by the user.

### 3.4 Abstention is a successful result

The model must be allowed to return `unknown`, `not_present`, `ambiguous`, or `needs_review`. Do not force every email into a category. Do not retry a refusal by changing the prompt to make the model answer.

## 4. Recommended first feature: bounded message triage

Implement one narrow feature first: **LLM-assisted triage and evidence extraction for already-prefiltered messages**.

The first version should return:

1. `relevance`: `financial_signal`, `possible_noise`, or `unknown`;
2. `signal_type`: `debit`, `reversal`, `failed_payment`, `atm_failure`, `invoice_overdue`, `refund`, `other`, or `unknown`;
3. extracted fields with provenance:
   - amount in paise;
   - currency;
   - transaction/reference ID;
   - channel;
   - event date;
   - reversal date;
   - merchant or counterparty;
   - explicit failure language;
4. short evidence summary using cautious language;
5. `needs_review` and a list of reasons;
6. exact source quotes or character spans for every extracted field.

Do not add automatic legal routing or compensation calculation in this phase.

## 5. Structured output contract

Use a strict JSON-schema response. Do not parse free-form prose. The response should be equivalent to:

```json
{
  "message_id": "string",
  "relevance": "financial_signal | possible_noise | unknown",
  "signal_type": "debit | reversal | failed_payment | atm_failure | invoice_overdue | refund | other | unknown",
  "amount": {
    "value_paise": "integer or null",
    "currency": "INR | unknown",
    "source_quote": "string or null",
    "status": "present | absent | ambiguous"
  },
  "transaction_reference": {
    "value": "string or null",
    "source_quote": "string or null",
    "status": "present | absent | ambiguous"
  },
  "event_date": {
    "value": "YYYY-MM-DD or null",
    "source_quote": "string or null",
    "status": "present | absent | ambiguous"
  },
  "reversal_date": {
    "value": "YYYY-MM-DD or null",
    "source_quote": "string or null",
    "status": "present | absent | ambiguous"
  },
  "channel": "UPI | ATM | CARD | NACH | MSME | OTHER | unknown",
  "counterparty": "string or null",
  "explicit_failure_language": "boolean",
  "evidence_summary": "string",
  "needs_review": "boolean",
  "review_reasons": ["string"],
  "model_version": "string"
}
```

Validation requirements:

- reject unknown enum values;
- reject negative amounts;
- reject dates outside a reasonable range;
- reject dates that do not have a source quote;
- reject amount values without a source quote;
- reject outputs with missing `message_id`;
- reject summaries containing legal-conclusion phrases;
- reject outputs whose extracted reference is not found in the supplied message text after normalization.

## 6. Prompt design

Use a system instruction that says:

> You are an evidence extraction assistant for Haq. Classify only the supplied email. Extract facts only when they appear in the supplied text. Return null or unknown when a fact is missing or ambiguous. Never decide whether a legal right exists, never calculate compensation, never cite a rule as confirmed, and never infer a date, amount, merchant, reversal, or transaction reference. Every extracted fact must include a short source quote. Use cautious evidence language.

The user payload should include only one message at a time during the first implementation. Do not ask the model to compare unrelated emails. Pairing a debit with a reversal remains deterministic: use normalized references and dates in Python, not model judgment.

Include adversarial examples in the prompt or evaluation set:

- promotional email containing an amount;
- OTP containing a long number;
- bank balance alert with no debit;
- debit without reversal;
- reversal without a matching debit;
- two different amounts in one thread;
- forwarded email with old dates;
- HTML email where the amount appears only in a footer;
- ambiguous date such as `03/04/26`;
- fake legal language inside a marketing email.

## 7. API and provider integration

Implement the LLM call server-side only. The browser must call Haq’s backend and must never receive the provider API key.

Recommended environment variables:

```text
LLM_PROVIDER=openai_compatible
LLM_API_BASE_URL=<provider base URL>
LLM_API_KEY=<server-side secret>
LLM_MODEL=<selected structured-output model>
LLM_TIMEOUT_SECONDS=20
LLM_MAX_MESSAGES_PER_SWEEP=100
LLM_MAX_MESSAGE_CHARS=8000
LLM_ENABLED=false
```

Default `LLM_ENABLED` to `false` until the deterministic test suite and redacted evaluation corpus pass. If the provider is unavailable, continue with the deterministic parser and label the result `llm_status: unavailable`; never fabricate an LLM result.

Before implementing bulk or parallel LLM calls, read the built-in model/API guidance available in the environment and confirm the exact structured-output request format supported by the chosen model. Use bounded concurrency and a per-sweep budget. Do not create one model request per entire mailbox.

## 8. Privacy and logging

Do not log message bodies, OAuth tokens, provider prompts, provider responses, or extracted personal details. Logs may contain:

- request ID;
- provider/model name;
- message count;
- latency;
- token usage if available;
- validation outcome;
- aggregate error category.

If debugging requires a message, use a redacted fixture stored only in the test corpus. Add a development-only explicit flag before logging any redacted payload, and keep it disabled in Render.

Do not persist LLM outputs in a database in this phase. Keep them in the existing transient request/session flow only.

## 9. Deterministic post-processing

After the LLM returns JSON:

1. Validate the schema with Pydantic.
2. Normalize whitespace, currency symbols, comma grouping, dates, and references.
3. Verify every source quote is a substring or normalized substring of the supplied message.
4. Compare extracted values with deterministic parser values.
5. Mark conflicts instead of choosing silently.
6. Apply the existing noise filters again.
7. Pair debit and reversal messages deterministically.
8. Create a candidate only if the existing candidate rules permit it.
9. Send candidates into the existing review UI.
10. Keep registry gating unchanged.

The LLM result must be an input to evidence review, not a replacement for the existing Gmail service contract.

## 10. Frontend requirements

The frontend should expose model assistance honestly:

- show “Evidence extraction assisted by AI” only when the LLM actually ran;
- show “Deterministic parser only” when the provider is disabled or unavailable;
- show an “AI suggestion” label next to model-derived values;
- show source quotes when the user expands a finding;
- show `Needs review` for ambiguity or conflicts;
- never show AI confidence as legal certainty;
- never hide provider errors;
- never make the user believe an LLM found a legally valid claim.

The existing DEMO MODE badge must remain visible for the synthetic inbox. A live Gmail result must never be labeled as demo.

## 11. Evaluation corpus

Create a redacted fixture corpus before enabling the feature. Minimum first corpus:

- 20 genuine-looking bank debit alerts;
- 15 reversal/refund alerts;
- 10 explicit failed-payment alerts;
- 10 ATM failure alerts;
- 10 overdue invoice messages;
- 20 promotional, OTP, shipping, social, and newsletter messages;
- 10 ambiguous or adversarial messages;
- 10 messages with missing amount/date/reference fields.

Each fixture should have a human-reviewed expected JSON record. Do not use real user inbox content. The fixture should record whether each field is present, absent, or ambiguous, plus the expected source quote.

Acceptance targets for the first release:

- zero invented dates, amounts, or references on the evaluation corpus;
- 100% schema-valid responses after validation or an explicit abstention;
- 100% of emitted extracted fields have source quotes;
- zero legal-conclusion phrases in evidence summaries;
- no candidate is created solely because the sender looks like a bank;
- deterministic counts remain unchanged when the LLM is enabled;
- provider failure produces a visible fallback status and no fake data.

## 12. Required tests

Add tests before enabling the feature in production:

### Contract tests

- valid structured response parses;
- malformed JSON is rejected;
- unknown enum values are rejected;
- missing source quote invalidates the extracted field;
- negative or unreasonable amounts are rejected;
- ambiguous dates remain `null` or `ambiguous`;
- legal-conclusion wording is rejected.

### Safety tests

- the provider never receives OAuth tokens;
- the provider payload is bounded in size;
- raw bodies never appear in API responses;
- no LLM output changes `emails_scanned`, `noise_filtered`, or `financial_alerts_found`;
- no LLM output bypasses registry verification;
- live mode still refuses Seeded entries;
- provider timeout returns a clear `llm_status` and deterministic results remain available;
- provider returns a wrong amount and deterministic/LLM conflict is surfaced;
- a promotional email containing ₹2,000 is not a candidate;
- a bank debit without failure/reversal evidence is not a violation.

### Regression tests

Run the complete existing suite:

```bash
python3 -m ruff check .
python3 -m pytest -q
cd web
npm run check
npm run build
```

Do not merge if any existing P0 test regresses.

## 13. Rollout plan

### Phase A — Shadow mode

Keep `LLM_ENABLED=false` for user-facing results. Run the LLM on the redacted fixture corpus and optionally on live messages only for aggregate metrics, with no output affecting candidates. Compare deterministic and LLM extraction results.

### Phase B — Assisted review

Enable LLM extraction for a small controlled path. Show model-derived values only as suggestions with source quotes. Candidates and calculations still use deterministic values. Keep a kill switch through `LLM_ENABLED=false`.

### Phase C — Bounded production

Enable the feature after evaluation targets pass. Keep provider timeout, request-size, message-count, and cost limits. Monitor only aggregate metrics. Do not add automatic legal routing.

### Phase D — Future work, not part of this handoff

Only after registry entries are independently verified may a future agent consider broader model assistance. Even then, the LLM must not become the authority for legal calculations or claim submission.

## 14. Handoff prompt for the next agent

Use this exact brief when delegating implementation:

> Implement Phase A of `docs/NEXT_LLM_INTEGRATION_SOP.md` in the Haq repository. Add a server-side, provider-agnostic LLM adapter behind `LLM_ENABLED=false`, a strict Pydantic structured-output schema, bounded one-message-at-a-time triage, source-quote validation, deterministic/LLM conflict reporting, redacted fixtures, and contract/safety tests. Do not alter registry gating, payment calculation, Gmail counts, candidate rules, OAuth behavior, or claim drafting. Do not use real inbox data. The provider must never receive OAuth tokens. Run Ruff, all Python tests, TypeScript check, and frontend build. Stop and report before enabling the feature or changing production environment variables.

## 15. Definition of done

This integration is ready for the next phase only when:

- the LLM adapter is disabled by default;
- structured output is schema-validated;
- every extracted field has source evidence;
- deterministic conflicts are visible;
- no legal conclusion is generated;
- no live registry gate is bypassed;
- no counts or candidate fields are invented;
- provider failures are safe and visible;
- all redacted evaluation and regression tests pass;
- the implementation and limitations are documented in the repository.
