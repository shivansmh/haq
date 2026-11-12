# a3-verify walkthrough

## Files

A3 adds `llm/verify.py` and `llm/trust.py`. The verification module provides pure helpers for whitespace, currency-symbol, Indian digit-grouping, reference, and date normalization. It verifies both that a source quote occurs in the original message and that the extracted value occurs inside the quote. Numeric dates remain rejected when day/month order is ambiguous without a known sender convention.

The trust module assigns T-A to deterministic values, T-B to AI suggestions verified in supplied text, and T-C to explicit user confirmations. It reports deterministic/model disagreements using the SOP conflict shape and provides a calculation guard that rejects T-B values.

`tests/test_llm_verify_trust.py` contains the A3 safety and contract tests. `docs/decisions.md` records the A3 decisions.

Nothing is wired into the live API, Gmail service, registry, or calculation engine.

## Tests

The tests cover fabricated values paired with real-looking quotes, quotes absent from the original message, values absent from otherwise valid quotes, currency and Indian grouping normalization, ambiguous dates, sender-specific date conventions, conflict reporting, explicit trust assignment, and rejection of T-B values as calculation inputs.

## Edge cases found

Currency matching must handle `₹`, `Rs`, `Rs.`, and `INR` forms while comparing paise rather than display formatting. Indian grouping such as `1,23,456` must compare equal to an ungrouped representation. References are compared without case or separator differences. A date such as `03/04/2026` cannot safely be interpreted without a sender convention, while an ISO date or a date with a textual month is unambiguous.

A quote that is present in the message is still insufficient if the extracted value is not inside that quote. A model value that disagrees with a deterministic value is reported as a conflict and is never silently replaced.

## Decisions logged

A3 decisions are appended to `docs/decisions.md`. The key decisions are that verification remains pure and unwired, ambiguous dates are rejected by default, T-B is evidence-only, and conflicts require user review.
