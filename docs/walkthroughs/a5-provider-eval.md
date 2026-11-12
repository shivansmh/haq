# a5-provider-eval walkthrough

## Provider and safety boundary

A5 uses Groq through `llm/groq_client.py`, targeting the OpenAI-compatible chat-completions endpoint. The adapter sends a shared system prompt first, then one bounded synthetic email payload. It uses temperature 0, strict JSON Schema response format, a hard completion-token cap, timeout handling, exponential retry for transient failures, and status mapping for unavailable, timeout, invalid-output, disabled, and successful responses.

The adapter reads `GROQ_API_KEY` only from the local environment. It does not log prompts, responses, API keys, or email bodies. The live API is not wired and `LLM_ENABLED` remains unchanged. With the owner-approved `$0` cap, a provider request is rejected before network I/O; no Groq request was made during this task.

Groq documentation was read before implementation. The current strict Structured Outputs models recorded in the decision log are `openai/gpt-oss-20b` and `openai/gpt-oss-120b`. Model IDs are configurable through `LLM_MODEL_TRIAGE`, `LLM_MODEL_EXTRACT`, and `LLM_MODEL_RECHECK`. Groq's current retention documentation says inference data is not retained by default, while reliability or abuse troubleshooting logs may be retained up to 30 days; Batch data is retained up to 30 days and was not used.

## Evaluation

`eval/run.py` applies the existing bounded redaction payload, runs triage and extraction, verifies emitted quotes, applies A3 trust-tier guards, and writes JSON metrics. Use `python -m eval.run --mock` for CI-safe evaluation. A non-mock run refuses to start unless `GROQ_SPEND_CAP_USD` is positive. The mock report includes event recall and precision by type, recall by sender template, field exact match, verified-quote rate, fabricated-field rate and upper bound, unknown/review rates, unseen-template recall, injection pass rate, calibration, cost per 100 emails, and p50/p95 latency.

The mocked unseen-split smoke run processed 40 synthetic fixtures and wrote `/tmp/haq-a5-mock.json`. It made no provider request. G1 and G2 numeric gates were recorded in `docs/decisions.md` before any real run.

## Tests

`tests/test_a5_groq_eval.py` covers zero-cap preflight blocking, transient retries, timeout mapping, request-body privacy, and required mock metrics. The complete repository suite and sensitive-data guard must pass before any future nonzero-cap synthetic run.
