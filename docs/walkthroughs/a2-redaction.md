# a2-redaction walkthrough

This task creates the privacy boundary immediately before a future provider adapter. It does not call an AI service. It receives one transient message, rejects credential-shaped input, masks identifiers, bounds the text, and returns a Pydantic provider payload plus a local-only provenance context.

## Files

- `llm/redact.py` detects credentials and sensitive identifiers.
- `llm/payload.py` defines the untrusted message input and builds the bounded `MessagePayload` from a1.
- `tests/test_llm_redaction.py` contains only synthetic values, assembled at runtime so the repository scanner does not mistake the test data for real identifiers.

## `llm/redact.py`

`from __future__ import annotations` postpones annotation evaluation. `re` supplies Python regular expressions. `dataclass` creates small immutable result records. `MappingProxyType` makes the token map read-only after construction. `Mapping` documents that callers receive a mapping rather than a mutable dictionary contract.

`SensitiveInputError` is a `ValueError` subclass for values that must not continue. `OAuthTokenDetected` is a narrower subclass so callers and tests can distinguish credential rejection without placing the credential in an exception message. The exception messages contain only category text, never input text.

The compiled patterns are constants. `PAN_PATTERN` matches the five-letters, four-digits, one-letter PAN shape. `AADHAAR_PATTERN` matches twelve digits with optional spaces or hyphens between three four-digit groups. `PHONE_PATTERN` matches a ten-digit Indian mobile-shaped number beginning with 6–9. `ACCOUNT_PATTERN` catches unseparated nine-to-eighteen digit runs that are not otherwise protected. `CARD_PATTERN` catches thirteen-to-nineteen digit card-like strings with optional spaces or hyphens.

`EMAIL_PATTERN` matches ordinary dotted-domain email addresses. `UPI_CONTEXT_PATTERN` finds a value after words such as UPI, VPA, payment ID, or payment address. `UPI_HANDLE_PATTERN` covers common PSP handles such as `okaxis`, `ybl`, and `paytm`. `UPI_GENERIC_PATTERN` covers a no-dot handle even when its provider suffix is not in the known list. UPI patterns are candidates for masking, not protected evidence.

`AMOUNT_PATTERN` protects currency-qualified values beginning with rupee, Rs, or INR. This is why a currency-qualified ten-digit amount survives while an unqualified ten-digit phone-shaped value is masked. `DATE_PATTERN` protects common numeric date forms. It does not interpret dates or decide legal meaning.

`REFERENCE_PATTERN` captures a token after reference, ref, RRN, transaction, or txn context. `SLASH_REFERENCE_PATTERN` captures a twelve-digit value between slashes. These reference spans are protected before generic Aadhaar and account matching. A standalone twelve-digit value has no evidence context and is conservatively masked.

`OAUTH_PATTERN` detects bearer tokens, common Google `ya29.` access-token shapes, Google refresh-token shapes beginning with `1//`, and explicit access/refresh-token assignments. Detection happens before any replacement. A detected credential raises `OAuthTokenDetected`, so it cannot reach a provider payload, log, or token map.

`_Candidate` is a private immutable record containing a start offset, end offset, and replacement label. Offsets refer to the original string, which makes right-to-left replacement safe.

`RedactionResult` has two parameters: `redacted_text` is the safe text and `token_map` maps placeholders such as `<PAN_1>` to original values. The map is wrapped in `MappingProxyType`, so a caller cannot mutate it. `restore(value)` is the only convenience method: it replaces placeholders in a provider quote with original values for local source verification. It never serializes the map. The object is transient and must not be logged or persisted.

`_spans(pattern, text, group=None)` returns match ranges. The optional `group` parameter selects a named capture group, which is needed because only the numeric value after `Ref` should be protected, not the word `Ref` itself. `_overlaps(start, end, spans)` determines whether two ranges intersect.

`_protected_spans(text)` runs the preservation patterns first. Amounts, dates, reference values, and slash-delimited references become protected ranges. UPI identifiers are deliberately excluded because they must be masked.

`_candidates(text)` collects all sensitive identifier matches with labels. The tuple order is the priority order. `_replace_sensitive(text)` sorts candidates by original position and length, skips protected or already-selected overlaps, and replaces from right to left so earlier offsets do not move. The counter dictionary creates deterministic labels such as `<PAN_1>` and `<EMAIL_1>`. The original value is inserted only into the in-memory map; the redacted text receives the placeholder.

`redact_sensitive(text)` is the public function. Its required `text` parameter must be a string. It first rejects OAuth-shaped input, then returns a `RedactionResult`. There is no optional logging flag and no serialization method by design.

## `llm/payload.py`

`MessageInput` is a frozen dataclass representing untrusted transient input. Its required parameters are `message_id`, `sender`, `subject`, `snippet`, and `body_text`; optional `received_at` defaults to `None`. It intentionally does not apply the provider's 8,000-character body limit because raw input must be redacted and bounded first.

`PreparedPayload` contains the Pydantic `MessagePayload` that a future provider adapter may receive and a tuple of local `RedactionResult` objects. The tuple preserves provenance for sender, subject, snippet, body, and timestamp. `restore_quote(quote)` tries each local map in memory. The class has no `model_dump`, `to_dict`, JSON, logging, or provider-send method. Callers must pass only `.payload` to a future provider.

`_normalise_sender(value)` case-folds and collapses whitespace. It has one required string parameter and returns a normalized safe sender string. `_require_opaque_message_id(value)` accepts only one-to-200-character alphanumeric, dot, underscore, colon, or hyphen identifiers. It rejects spaces, email-like values, and other PII-shaped identifiers rather than trying to invent an opaque replacement.

`_bound_fields(subject, snippet, body_text, cap)` applies the required integer `cap` to the combined subject, snippet, and body. Subject is additionally limited to 500 characters and snippet to 2,000 characters. The body receives whatever budget remains. This is deterministic truncation from the beginning of each field; it does not log or persist the discarded suffix.

`build_provider_payload(message, settings=None)` is the public builder. `message` is required and must be a `MessageInput`. The optional `settings` parameter exists for production configuration injection and safe tests; when omitted, `load_settings({})` supplies disabled safe defaults without reading a secret from the test environment. The function validates the opaque ID, redacts every text field, applies the combined character cap, normalizes the sender, and constructs the existing strict `MessagePayload`. It returns `PreparedPayload`, keeping the maps available only for local quote checking.

The returned provider payload contains exactly the a1 fields: `message_id`, normalized redacted sender, bounded subject, bounded snippet, bounded body text, and optional timestamp. It contains no OAuth credential, token map, raw body beyond the cap, or hidden configuration.

## Tests and current ambiguity examples

The corpus tests PAN, grouped Aadhaar, phone, account, card, email, UPI ID, currency-qualified ten-digit amount, contextual twelve-digit references, slash-delimited references, and dates. It also checks that a bearer/Google-shaped token is rejected and that an AST scan finds no logging call in `llm/` that receives payload/body variables.

Known conservative false-positive behavior: an unqualified twelve-digit number is masked even if a human might know it is a transaction reference; callers must provide reference context. An unqualified ten-digit number is masked even if it might be a large amount; currency context preserves such amounts. A generic no-dot `local@handle` is treated as a UPI ID and masked, which is safer than forwarding a possible payment address.

Known false-negative boundary: this regex layer does not promise detection of every national identifier format, obfuscated credential, image-only text, or every future PSP handle. It does detect generic no-dot handles and fails closed on common OAuth token shapes. OCR and provider-specific token formats require a future, separately tested task.

No AI API choice is required here. Before a real provider adapter is implemented, the owner must choose the provider/model and approve the exact structured-output transport after reviewing the built-in model/API guidance. That choice is intentionally not encoded in a2.
