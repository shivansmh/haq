# Haq GitHub Pages deployment

The Lovable frontend lives in `shivansmh/haq-noir-gold` and is deployed as a static SPA at:

`https://shivansmh.github.io/haq-noir-gold/`

The frontend calls the existing Render API at `https://haq-api-u3pz.onrender.com`. The Pages build is
run by `.github/workflows/pages.yml`; it creates `dist/index.html`, copies it to `dist/404.html` for
TanStack Router deep links, and publishes the artifact through GitHub Pages.

For Gmail OAuth to work in production, the Google OAuth client must allow this callback URI:

`https://haq-api-u3pz.onrender.com/v1/gmail/callback`

The Render service must use these non-secret values:

- `FRONTEND_ORIGINS=http://localhost:5173,https://shivansmh.github.io`
- `FRONTEND_URL=https://shivansmh.github.io/haq-noir-gold`
- `OAUTH_REDIRECT_URI=https://haq-api-u3pz.onrender.com/v1/gmail/callback`

`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and any Groq key remain secrets. GitHub Pages hosts only
frontend assets; Gmail tokens and sweep processing remain server-side in the Render API.
