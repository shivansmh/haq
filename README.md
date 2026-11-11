# Haq

Haq is a hackathon prototype for helping people act on documented rights involving failed payments, delayed MSME dues, and unclaimed assets in India.

## T0 foundation

This repository now contains the contract-first T0 foundation from the technical build plan:

- FastAPI stub with the planned endpoint surface.
- Fixed demo fixtures with explicit `UNVERIFIED RULE` stamps.
- Initial registry and research-conflict locations.
- Privacy policy, decision log and sensitive-data pre-commit guard.
- Pytest, Ruff and GitHub Actions CI.
- Reserved directories for the engine, ingest, cleaning, matching, claims, data and web client.

T0 deliberately performs **no legal calculation, statement parsing, persistence, portal automation or filing**. T1 will make the registry machine-readable and verified before calculation code is added.

## Run locally

```bash
python3 -m venv .venv
. .venv/bin/activate
make install
make install-hooks
make lint
make test
make run
```

Then open `http://127.0.0.1:8000/docs` or inspect `http://127.0.0.1:8000/openapi.json`.

## Safety boundary

Use synthetic or genuinely redacted examples only. Never commit bank statements, PAN, Aadhaar, account numbers or other personal data. `data/real/` is Git-ignored. Haq reports what documented rules say; it is not legal advice and does not file claims on a user's behalf.

See [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md), [`docs/DATA_POLICY.md`](docs/DATA_POLICY.md) and [`docs/decisions.md`](docs/decisions.md) for the T0 contract and decisions.
