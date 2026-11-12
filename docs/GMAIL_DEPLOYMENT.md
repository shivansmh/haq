# Gmail sweep deployment

The frontend is a static GitHub Pages site. Gmail OAuth must run on a separate HTTPS backend because GitHub Pages cannot hold a Google client secret or exchange authorization codes securely.

## Google Cloud setup

Create or select a Google Cloud project, enable the Gmail API, and configure the OAuth consent screen. Add the deployed API domain to Authorized domains. Add this restricted scope to the Data Access page:

```text
https://www.googleapis.com/auth/gmail.readonly
```

Create a Web application OAuth client. Set its authorized redirect URI to:

```text
https://YOUR-API-HOST/v1/gmail/callback
```

The public app also needs a same-domain privacy-policy URL that explains that Gmail content is used only for the inbox sweep, is processed transiently, and is not retained after the scan.

## Render deployment

1. Create a new Render Web Service from this repository and use `render.yaml`, or enter `pip install -r requirements.txt` as the build command and `uvicorn api.main:app --host 0.0.0.0 --port $PORT` as the start command.
2. Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` as secrets.
3. Set `OAUTH_REDIRECT_URI` to `https://YOUR-API-HOST/v1/gmail/callback`.
4. Set `FRONTEND_ORIGIN` to `https://shivansmh.github.io` (origin only, no `/haq`).
5. Set `FRONTEND_URL` to `https://shivansmh.github.io/haq` (the full Pages URL).
6. Set `COOKIE_SECURE=true`.

### Optional Groq email assistance

The live Gmail scan can make one synchronous Groq extraction request per deterministically prefiltered financial message. It sends only the A2-redacted, bounded payload (default combined text cap: 8,000 characters); noise is skipped. A3 verifies source quotes and leaves model fields at trust tier T-B. Model suggestions and conflicts are shown for review only and never modify deterministic candidates or calculation inputs. Prompts, responses, raw bodies, and redaction token maps are not logged or persisted.

Add these **backend environment variables** in Render (never in GitHub Pages or frontend `VITE_*` settings):

```text
GROQ_API_KEY=<server-side secret>
LLM_ENABLED=true
GROQ_SPEND_CAP_USD=<positive finite cap in USD>
LLM_MAX_MESSAGES_PER_SWEEP=10
LLM_MAX_MESSAGE_CHARS=8000
LLM_TIMEOUT_SECONDS=20
LLM_MODEL_EXTRACT=openai/gpt-oss-20b
```

`GROQ_API_KEY` alone does not enable calls. `LLM_ENABLED` defaults to `false`, and the spend ceiling defaults to `$0`, which blocks provider requests before network I/O. Pick a cap you explicitly accept; the current Groq client's budget is shared by the API process and resets when that process restarts. The model allowlist is limited to models with configured pricing so unknown model names fail closed. Keep the per-sweep message limit low for a hackathon deployment. The sweep response reports whether AI actually ran or the deterministic-only fallback was used.

Enter `GROQ_SPEND_CAP_USD` as a plain positive decimal such as `0.05` (without `$` or commas), and choose the amount you are comfortable allowing. Invalid optional Groq settings now fall back to deterministic-only email processing rather than breaking the Gmail scan.

`GET /healthz` includes a non-secret `groq_status` (`disabled`, `missing_key`, `zero_spend_cap`, `invalid_spend_cap`, `unsupported_model`, or `ready`). It reports no credential or cap value and does not call Groq.

The OAuth session store is intentionally in memory for the hackathon demo. For a multi-instance production service, replace it with encrypted server-side session storage and rotate/revoke refresh tokens on disconnect.

## GitHub Pages variable

Add a repository Actions variable named `HAQ_API_URL` with the API origin, for example `https://haq-api.example.com`. The Pages workflow injects it as `VITE_API_BASE_URL` during the Vite build. If it is absent, the frontend still runs in demo mode and local development uses `http://localhost:8000`.
