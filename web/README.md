# Haq web client

The live demo is published at [shivansmh.github.io/haq](https://shivansmh.github.io/haq/).

The client is a mobile-first, editorial sweep experience: it explains Gmail consent before connecting, filters a sample inbox or a real connected inbox, shows source-backed findings, keeps uncertainty visible, and prepares a draft the user files themselves.

## Local development

```bash
npm install
npm run dev
```

The client uses `http://localhost:8000` as its local API origin. Run the backend from the repository root:

```bash
python server.py
```

Live Gmail OAuth needs the Google Cloud and backend variables described in [`docs/GMAIL_DEPLOYMENT.md`](../docs/GMAIL_DEPLOYMENT.md). The browser does not accept or store access tokens; the backend owns the OAuth exchange and HttpOnly session cookie.

## GitHub Pages

Pages deploys automatically from `main` through `.github/workflows/pages.yml`. Set the repository Actions variable `HAQ_API_URL` to the deployed HTTPS API origin before using live Gmail. Without that variable, the public site remains safe demo mode and the sample inbox still works.
