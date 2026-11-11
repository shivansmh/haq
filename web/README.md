# Web client

The live demo is published at [shivansmh.github.io/haq](https://shivansmh.github.io/haq/).

This is the React/Vite client. The API contract is available before the client was scaffolded, so the frontend starts in mock mode and can be switched to the FastAPI backend with `VITE_API_MODE=real` when the backend is deployed at the same origin.

```bash
npm install
npm run dev
```

GitHub Pages deploys automatically from `main` through `.github/workflows/pages.yml`.
