# a1-config-schema walkthrough

This walkthrough explains the first LLM-layer foundation without assuming that the owner knows Pydantic, dataclasses, generics, abstract classes, or Python environment handling. This task adds contracts only. It does not call a provider, send a message, read an OAuth token, or enable the feature.

## What was added

The `llm/` package contains four Python modules and one data file:

- `config.py` reads the provider configuration safely.
- `models.py` defines the schema-v2 payload and result models.
- `validate.py` applies checks that depend on the supplied message text.
- `client.py` defines the provider-neutral interface plus disabled and fake clients.
- `data/legal_conclusion_phrases.txt` is the editable phrase list used by validation.

`api/schemas.py` adds one optional `llm_status` field to the existing `ClassifyResponse`. Because the field has a default of `None`, old callers do not need to send it and old response construction remains valid.

## `llm/config.py`

`from __future__ import annotations` postpones evaluation of type annotations. This keeps annotations readable and avoids problems when a type refers to another type defined later.

`import math` supplies `isfinite`, which rejects NaN and infinity. `import os` gives production code access to `os.environ`. `dataclass` creates a small data object without hand-writing its initializer. `Mapping` describes any read-only dictionary-like environment source, which lets tests pass a synthetic mapping instead of inspecting the machine's real environment. `urlparse` checks that an optional provider URL uses `http` or `https`.

`@dataclass(frozen=True, slots=True)` makes `LLMSettings` immutable and memory-efficient. `frozen=True` means assigning to `settings.enabled` fails after construction. `slots=True` prevents accidental extra instance attributes. The fields mirror SOP v2 section 7: provider, base URL, secret key, model, timeout, per-sweep message cap, per-message character cap, and the kill switch. The safe defaults are disabled, 20 seconds, 100 messages, and 8,000 characters. The default API key and URL are `None`; the code never invents credentials.

`_read_bool(raw, name)` strips whitespace and accepts only explicit true/false spellings. Its `name` parameter is included in the error so an operator can identify the bad environment variable. Unknown spellings fail instead of silently turning on or off.

`_read_positive_int(raw, name)` converts a string to an integer and rejects zero and negative values. `_read_positive_float(raw, name)` does the analogous work for the timeout and additionally rejects non-finite values. The `raw` parameter is the environment text and `name` is the error label.

`load_settings(environ=None)` is the public constructor. The optional `environ` parameter exists for safe tests and deterministic callers; when omitted, production reads `os.environ`. It reads each SOP variable, validates it, and returns a new frozen `LLMSettings` object. The `source.get(key, default)` calls provide defaults without requiring a secret. If `LLM_ENABLED=true`, both an HTTPS/HTTP base URL and an API key must be present; this fails closed rather than creating a half-configured live client.

## `llm/models.py`

The module imports `date` for date-only values, `Enum` for closed sets, and `Generic`/`TypeVar` for reusable quoted fields. Pydantic's `BaseModel` supplies parsing and validation. `ConfigDict(extra="forbid")` rejects fields that were not part of the contract, which prevents a provider response from smuggling in unreviewed attributes. `Field` adds length and default constraints. `field_validator` validates one field, and `model_validator` validates relationships between fields.

`LLMStatus` is a string enum with exactly five values: `disabled`, `unavailable`, `timeout`, `invalid_output`, and `ok`. Returning strings while storing enum members keeps JSON output readable and bounded.

`TrustTier` deliberately names evidence provenance rather than legal confidence: `deterministic`, `llm_suggestion`, and `user_confirmed`. The LLM default is `llm_suggestion`; no model result is a legal conclusion.

`Relevance`, `SignalType`, `FieldStatus`, `Currency`, and `Channel` are closed enums. Pydantic rejects a misspelled or invented value instead of accepting it as arbitrary text. `unknown`, `other`, and `ambiguous` are explicit abstention values where the SOP permits uncertainty.

`MessagePayload` is the only input shape accepted by the clients. Its `message_id` is required and non-empty. Sender, subject, snippet, body text, and received timestamp are bounded. `body_text` is capped at 8,000 characters, matching the SOP. `extra="forbid"` means tokens, cookies, attachments, or hidden configuration cannot be added accidentally.

`FieldWithQuote[T]` is a generic reusable field. `T` is a type placeholder: one instance can be a string reference or a `date`. Every field has a `value`, an optional `source_quote`, and a `status`. A present field must have a value; a value must be marked present and must have a quote; an absent field cannot carry a quote. The optional `source_quote` is capped at 240 characters. The field validator also rejects negative integers, which protects generic integer fields.

`AmountWithQuote` is the amount-specific sibling. It uses the exact SOP name `value_paise`, not rupees or floating-point numbers. Its validator rejects negative paise and its model validator enforces the same presence/quote relationship. Keeping the amount name explicit prevents a caller from confusing paise with display-formatted rupees.

`Conflict` records a deterministic value and an LLM suggestion without choosing between them. Its `status` and `action` patterns are intentionally narrow: a conflict is visible and the action is `ask_user`.

`Event` represents an event type and optional event date. If an event date exists, its own quote is required. This model does not calculate a deadline or choose a registry rule.

`TriageResult` contains only classification, cautious evidence language, review flags, and model version. `ExtractionResult` contains the message ID, enums, quoted amount/reference/date fields, channel, counterparty, explicit failure flag, cautious summary, review information, model version, and trust tier. It contains no rule ID, compensation amount, entitlement decision, or confidence upgrade.

## `llm/validate.py`

Pydantic catches local shape errors. `validate_extraction(result, message)` catches errors that require comparing the result to the actual bounded message. `DATE_MIN` and `DATE_MAX` are defensive configured parsing bounds. `QUOTE_MAX_CHARS` documents the quote limit in one place.

The phrase file is read relative to the module with `Path(__file__).parent`, so the validator does not depend on the process working directory. Blank lines and comment lines are ignored, and the final collection is a `frozenset`, preventing accidental mutation and duplicate behavior.

`_normalise_text` performs case-folding and whitespace collapsing for quote matching. `_normalise_reference` removes non-alphanumeric characters so harmless punctuation differences do not make a reference appear absent. Neither function invents a value.

`_check_quoted_field(field_name, value, quote, message_text)` receives the field label, extracted value, quote, and combined bounded message text. It rejects a non-null value with no quote, an over-long quote, or a quote that is not present in normalized message text. `field_name` makes the error useful without logging message content.

`_check_date(field_name, value)` rejects dates outside the configured range. The range is a parser guard, not a legal rule. `_check_legal_language(result)` searches only the generated summary and review reasons. Source quotes are evidence and may contain words that the sender wrote; they are not treated as Haq's legal conclusion.

`validate_extraction` first checks that the result belongs to the supplied `message_id`. It checks date bounds before quote matching, then checks amount, reference, event date, and reversal date quotes. It separately verifies that a normalized reference occurs in the supplied message. Finally it rejects legal-conclusion phrases and returns the same validated result for convenient chaining.

## `llm/client.py`

`ABC` and `abstractmethod` define an interface without choosing a provider. `LLMClient` requires `triage(payload)` and `extract(payload)`, each accepting one already-prefiltered `MessagePayload`. The interface is intentionally one message at a time; bulk mailbox transport is not part of this task.

`LLMResponse[T]` is a frozen generic dataclass. `T` is the result type, `llm_status` is always one of the five status enum values, `result` is optional because disabled or invalid calls must not fabricate data, and `error` is optional for an aggregate-safe error category. The response does not store prompts, bodies, tokens, or provider output logs.

`DisabledClient` implements both abstract methods and returns only `LLMStatus.DISABLED` with no result. `payload` is still part of the method signature because it preserves the interface; it is not inspected or logged.

`FakeClient` is a deterministic test double. Its optional `invalid` parameter selects the invalid canned path without a provider call. The valid `triage` response uses cautious wording and asks for review. The valid `extract` response uses a synthetic amount quote and then calls `validate_extraction` before returning `ok`. The invalid path returns `invalid_output` and no result. This demonstrates the intended behavior for a future provider adapter: parse, validate, and expose a safe status rather than returning unchecked output.

## `api/schemas.py`

The `Literal[...] | None` field keeps the API status vocabulary closed while preserving backward compatibility. `None` means that an existing response did not run the LLM layer. The field is optional and does not alter existing required fields, candidate rules, counts, registry gating, or calculations.

## Tests and future changes

`tests/test_llm_foundation.py` covers safe defaults, immutability, environment parsing, negative caps, every enum and provenance rule, date range, message IDs, quote length, legal phrase loading, reference presence, disabled behavior, fake valid/invalid round trips, and the optional API field. A future real provider must implement `LLMClient`, use only `MessagePayload`, validate every output with `validate_extraction`, and preserve the same status semantics. It must not be added by changing this task's defaults or by bypassing these checks.
