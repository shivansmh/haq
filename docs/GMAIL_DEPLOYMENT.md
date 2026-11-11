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

The OAuth session store is intentionally in memory for the hackathon demo. For a multi-instance production service, replace it with encrypted server-side session storage and rotate/revoke refresh tokens on disconnect.

## GitHub Pages variable

Add a repository Actions variable named `HAQ_API_URL` with the API origin, for example `https://haq-api.example.com`. The Pages workflow injects it as `VITE_API_BASE_URL` during the Vite build. If it is absent, the frontend still runs in demo mode and local development uses `http://localhost:8000`.
