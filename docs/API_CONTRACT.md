# T0 API contract

The canonical machine-readable contract is the FastAPI-generated OpenAPI document available at `/openapi.json` when the stub runs. The endpoint set follows the technical plan.

| Method | Path | T0 behaviour |
|---|---|---|
| GET | `/healthz` | Returns version, demo mode and registry load summary. |
| GET | `/v1/registry` | Returns fixed seeded summaries; no rule is computed. |
| GET | `/v1/registry/{id}` | Returns a contract fixture and linked conflicts. |
| POST | `/v1/ingest` | Accepts text metadata and returns an explicit not-implemented report. |
| POST | `/v1/detect` | Accepts transaction rows and returns no candidates. |
| POST | `/v1/compute/payment` | Requires confirmation and returns a clearly stamped fixture. |
| POST | `/v1/compute/msme` | Returns a stamped non-computing fixture. |
| GET/POST | `/v1/unclaimed/guide` | Returns an empty guide without portal automation. |
| POST | `/v1/claims/draft` | Returns a placeholder only; nothing is filed. |
| POST | `/v1/gmail/sweeps` | Starts one per-session bounded Gmail sweep and returns a job id immediately. |
| GET | `/v1/gmail/sweeps/{id}` | Returns job state, elapsed time and real listed/triaged/analysed/relevant/not-analysed counts. |
| DELETE | `/v1/gmail/sweeps/{id}` | Requests cancellation of the in-memory sweep. |

All T0 responses are demo fixtures. They must not be presented as verified legal calculations.

Background sweeps are transient. A provider limit, host restart or free-instance sleep can end a
job; clients must show the returned partial-coverage counts and offer a new sweep rather than
inventing completion.
