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
- **Synthetic evaluation revision:** failed-payment precision is not a valid parser metric because a statement cannot prove failure. T2 evaluation now records pairing accuracy against `expected_label` and true-failure candidate coverage against `is_true_failure`.
- **Synthetic baseline:** the supplied 20-statement, four-layout corpus yields 100% pairing accuracy and 80% true-failure candidate coverage. These are synthetic-only figures, not the real-data gate.
- **UPI references:** slash-delimited 12-digit UPI references and the labelled synthetic `reference` column are safe test identifiers; the scanner exempts only those contexts and continues to flag PAN, grouped Aadhaar, email, phone and other long digit patterns.

## 2026-11-12 — a1-config-schema

- **LLM rollout:** the provider-agnostic client is disabled by default through `LLM_ENABLED=false`; this follows LLM SOP v2 section 7 and preserves deterministic-only user results until a later rollout decision.
- **LLM trust:** extracted values default to `llm_suggestion`; `deterministic` and `user_confirmed` remain explicit tiers, and no LLM tier is treated as legal authority.
- **Evidence contract:** every non-null extracted amount or date requires a bounded source quote; references also require normalized presence in the supplied bounded message. This mirrors SOP v2 sections 5 and 9.
- **Date range:** schema validation accepts evidence dates from 2000-01-01 through 2100-12-31. The bounds are defensive parsing limits, not legal assumptions, and can be revisited with a dated decision.
- **Quote limit:** source quotes are capped at 240 characters while message bodies remain capped at 8,000 characters, preserving the SOP's bounded-message rule without returning raw bodies.
- **Status propagation:** `llm_status` is optional in the existing classification response and uses only `disabled`, `unavailable`, `timeout`, `invalid_output`, or `ok`; existing response fields remain unchanged.
- **Provider scope:** this task intentionally adds no network provider, OAuth handling, environment enabling, prompt transport, or persistence.

## 2026-11-12 — a2-redaction

- **Redaction order:** reference, amount, date, and contextual UPI spans are identified before generic identifier masks. This preserves evidence while preventing 12-digit UPI references from being mistaken for Aadhaar-shaped data.
- **Reference policy:** a 12-digit value is preserved only between slashes or after explicit `reference`, `ref`, `RRN`, `transaction`, or `txn` context. A standalone 12-digit value is conservatively masked.
- **Amount policy:** a 10-digit amount is preserved only when attached to `₹`, `Rs`, or `INR` context. A standalone 10-digit value is treated as phone/account-like and masked.
- **Token-map lifetime:** redaction maps are immutable in-memory mappings attached only to the transient preparation result. The provider payload contains no map field and there is no serialization function for maps.
- **Payload cap:** the configured character cap applies to the combined subject, snippet, and body text after redaction; sender and timestamp remain bounded by the Pydantic payload model. No body is logged.
- **Credential handling:** bearer, Google access/refresh-token-shaped, and explicit `access_token`/`refresh_token` inputs fail closed before redaction rather than being forwarded or logged.
- **AI provider choice:** no provider decision is needed for a2 because this task adds no provider call. Provider selection must be made before implementing the first real adapter.
- **Redactor boundary:** `clean/redact.py` keeps its existing string-returning contract for statement normalization; `llm/redact.py` is a separate provenance-aware boundary because changing the clean contract would regress deterministic parsing and the LLM path needs an immutable token map.

## 2026-11-12 — a3-verify

- **Verification boundary:** A3 exposes pure normalization, quote verification, trust assignment, conflict reporting, and calculation-safety helpers only; no live API or Gmail behavior is changed.
- **Quote provenance:** a quote must occur in the original message after conservative whitespace, currency, and digit-grouping normalization, and the extracted value must also occur inside that quote.
- **Date ambiguity:** numeric dates with both day and month at or below 12 are rejected unless a known sender convention (`DMY` or `MDY`) is supplied. ISO and textual month forms remain unambiguous.
- **Trust tiers:** T-A is deterministic, T-B is AI-suggested and text-verified, and T-C is explicitly user-confirmed. T-B values are rejected by the calculation input guard.
- **Conflict handling:** deterministic/model disagreements produce the SOP JSON shape with `status=conflict` and `action=ask_user`; no side is selected silently.

## 2026-11-12 — a4-prompts-fixtures

- **Provider boundary:** A4 contains prompt text, a local category builder, a deterministic generator, labels, and tests only. No provider, tool, network, or live API call is made.
- **Synthetic corpus:** all 155 fixtures are invented and marked synthetic. The corpus has 115 base fixtures plus 40 dedicated injection/adversarial fixtures. Sender organizations, references, codes, and amounts are generated placeholders and never copied from real inboxes.
- **Prompt injection:** email content is delimited as data. Embedded instructions are ignored as instructions and surfaced through `review_reasons`; no email text can change the prompt contract.
- **Splits:** 70 fixtures are dev, 45 are held-out, and 40 are unseen. The prompt files contain no fixture examples, so the prompt-example template set is empty and cannot overlap unseen templates.
- **Labels:** each fixture has a JSON label with event list, field status, expected quotes, review reasons, split, template ID, and blank reviewer initials for independent human review.

## 2026-11-12 — a5-provider-eval Groq preflight

- **Provider substitution:** A5 uses Groq through `llm/groq_client.py`, not Anthropic. The client targets Groq's OpenAI-compatible `POST /openai/v1/chat/completions` endpoint.
- **Structured outputs:** Groq's current Structured Outputs documentation specifies `response_format: {type: "json_schema", json_schema: {name, strict, schema}}`. Strict mode requires every property to be required and every object to set `additionalProperties: false`; provider schema checks remain deliberately conservative, with range, pattern, and date checks retained in Pydantic.
- **Models:** Groq currently lists `openai/gpt-oss-20b` and `openai/gpt-oss-120b` as strict Structured Outputs models. Model IDs are supplied through `LLM_MODEL_TRIAGE`, `LLM_MODEL_EXTRACT`, and `LLM_MODEL_RECHECK`, with no hard-coded production selection.
- **Retention:** Groq's current data documentation says inference customer data is not retained by default, but reliability or abuse troubleshooting logs may be retained for up to 30 days. Batch input/output files are retained for up to 30 days unless deleted earlier. Usage metadata is always retained and does not include customer inputs or outputs. Zero Data Retention is available as a control; A5 does not use Batch and sends synthetic fixtures only.
- **Evaluation gate:** The owner-approved hard spend cap is currently `$0` per run. Therefore `eval/run.py --mock` is the only executable evaluation mode in this phase; the real adapter refuses to send a request until a nonzero cap is explicitly configured.
- **G1 target:** On the dev split, at least 95% schema-valid or explicit-abstention outputs, at least 95% verified-quote rate for emitted fields, zero fabricated fields, and 100% injection pass rate are required before any controlled assisted-review trial.
- **G2 target:** On held-out and unseen-template splits, at least 90% event recall and 90% event precision per required event type, at least 90% field exact match, zero fabricated fields, at least 95% injection pass rate, and no more than 10% absolute calibration error are required before any non-mock provider run is considered. These are evaluation gates, not claims about current performance.

## 2026-11-12 — live Gmail Groq assistance wiring

- **Scope:** Optional Groq extraction now runs only on messages selected by the existing deterministic financial prefilter, one message per request and up to `LLM_MAX_MESSAGES_PER_SWEEP`. Synthetic demo sweeps remain provider-free.
- **Privacy:** Provider input is built via the existing A2 redaction and combined text cap. API-returned sender, subject, snippet, candidate source, model summaries, review reasons and source quotes are redacted; bodies and A2 token maps are not serialized or persisted.
- **Authority:** Existing deterministic results and candidate fields remain unchanged. Model values are attached as quote-verified T-B suggestions; A3 ambiguity/conflict handling is applied, and T-B values do not enter calculations.
- **Spend:** `LLM_ENABLED` defaults to false and `GROQ_SPEND_CAP_USD` defaults to zero. Unsupported model IDs fail closed. The Groq budget is shared by the backend process and resets on process restart; the app operator must set an explicitly accepted positive cap before network calls can occur.
- **Deployment gate:** Render must receive `GROQ_API_KEY`, `LLM_ENABLED=true`, an explicit positive `GROQ_SPEND_CAP_USD`, and appropriate message/time limits. No secret is included in the repo or frontend.
