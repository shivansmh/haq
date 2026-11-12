# Haq GitHub Pages deployment

The canonical Haq repository contains both the backend and the Lovable frontend:

- Repository: `https://github.com/shivansmh/haq`
- Frontend source: `web/`
- Pages URL: `https://shivansmh.github.io/haq/`
- API: `https://haq-api-u3pz.onrender.com`

The root `.github/workflows/pages.yml` builds `web/` as a static SPA, copies `index.html` to
`404.html` for TanStack Router deep links, and publishes the artifact through GitHub Pages.

For Gmail OAuth, the Google OAuth client must allow:

`https://haq-api-u3pz.onrender.com/v1/gmail/callback`

Render should use:

- `FRONTEND_ORIGINS=http://localhost:5173,https://shivansmh.github.io`
- `FRONTEND_URL=https://shivansmh.github.io/haq`
- `OAUTH_REDIRECT_URI=https://haq-api-u3pz.onrender.com/v1/gmail/callback`

GitHub Pages hosts only frontend assets. Gmail tokens and sweep processing remain server-side in the
Render API.
