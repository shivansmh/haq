# Data policy

Haq is a demo-grade, memory-only prototype. The repository may contain only synthetic or genuinely redacted data. Never commit bank statements, PAN, Aadhaar, account numbers, phone numbers, email addresses or other personal data.

## Runtime

- Uploads are intended to be processed in memory and discarded after the request.
- Request bodies, narrations, filenames and amounts must not be logged.
- `data/real/` is ignored by Git and must remain empty in shared work.
- T0 does not persist users, sessions, claims or files.
- The flagged-record ledger is held in process memory, keyed by an opaque session id, and expires
  with the Gmail session (one hour). It keeps only the redacted structured record, never an email
  body. It caps the number of sessions and evicts the oldest first.

## Pre-commit protection

Run `make install-hooks` once per checkout. The hook invokes `scripts/check_sensitive.py` and rejects PAN-shaped text, Aadhaar-shaped 12-digit numbers and long account-number-shaped digit runs. This is a guardrail, not proof that a file is safe; review every fixture manually.

## Product boundary

Haq reports what documented rules say. It does not provide legal advice, guarantee recovery, log into portals, scrape portals or file a claim on a user's behalf.
