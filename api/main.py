from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from engine.registry_loader import load_registry

from .fixtures import health_payload
from .schemas import (
    ClaimDraftRequest,
    DetectRequest,
    GuideRequest,
    IngestRequest,
    MsmeComputeRequest,
    PaymentComputeRequest,
)

REGISTRY = load_registry()


app = FastAPI(
    title="Haq API",
    version="0.1.0-t1",
    description=(
        "T1 registry-backed stub. Seeded research data only; "
        "no legal calculation or persistence."
    ),
)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": "HTTP_ERROR",
            "message": str(exc.detail),
            "field": None,
            "request_id": request.headers.get("x-request-id", str(uuid4())),
        },
    )


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    payload = health_payload()
    payload["registry"] = {
        "loaded": len(REGISTRY.all()),
        "verified": sum(entry.status == "Verified" for entry in REGISTRY.all()),
        "seeded": sum(entry.status == "Seeded" for entry in REGISTRY.all()),
        "parked": sum(entry.status == "Parked" for entry in REGISTRY.all()),
    }
    return payload


@app.get("/v1/registry")
def registry() -> dict[str, Any]:
    return {
        "items": [
            {
                "id": entry.id,
                "name": entry.name,
                "status": entry.status,
                "confidence": entry.confidence,
            }
            for entry in REGISTRY.all()
        ],
        "mode": "demo",
    }


@app.get("/v1/registry/{right_id}")
def registry_entry(right_id: str) -> dict[str, Any]:
    try:
        entry = REGISTRY.get(right_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "id": entry.id,
        "name": entry.name,
        "status": entry.status,
        "confidence": entry.confidence,
        "sources": [source.model_dump(mode="json") for source in entry.sources],
        "conflicts": entry.conflict_ids,
        "unresolved": entry.unresolved_fields(),
        "note": "Registry data is seeded and unverified until the research gates pass.",
    }


@app.post("/v1/ingest")
def ingest(payload: IngestRequest) -> dict[str, Any]:
    return {
        "status": "stub",
        "mode": "demo",
        "stamp": "UNVERIFIED RULE",
        "parse_report": {"accepted": False, "reason": "T2 ingest adapters are not implemented yet"},
        "transactions": [],
        "input_received": bool(payload.text or payload.filename),
    }


@app.post("/v1/detect")
def detect(payload: DetectRequest) -> dict[str, Any]:
    return {
        "status": "stub",
        "mode": "demo",
        "stamp": "UNVERIFIED RULE",
        "candidates": [],
        "input_rows": len(payload.transactions),
        "note": "Candidates require T2 ingest and pairing; no claim is inferred here.",
    }


@app.post("/v1/compute/payment")
def compute_payment(payload: PaymentComputeRequest) -> dict[str, Any]:
    deadline = payload.debit_date + timedelta(days=1)
    if not payload.confirmed:
        return {
            "status": "confirmation_required",
            "right_id": payload.right_id,
            "mode": "demo",
            "stamp": "UNVERIFIED RULE",
            "message": "Confirm the event before any result is computed.",
        }
    return {
        "right_id": payload.right_id,
        "mode": "demo",
        "stamp": "UNVERIFIED RULE",
        "deadline": deadline.isoformat(),
        "delay_days": {"low": 0, "high": 0},
        "amount_paise": {"low": 0, "high": 0},
        "unresolved": ["reversal_day_counts"],
        "conflicts": ["C5"],
        "confidence": "Low",
        "trace": [{
            "step": 1,
            "text": "T0 fixture only: T+1 is shown as a placeholder and is not a verified rule.",
            "clause": "to be confirmed from primary source",
            "inputs": {
                "debit_date": payload.debit_date.isoformat(),
                "amount_paise": payload.amount_paise,
            },
        }],
    }


@app.post("/v1/compute/msme")
def compute_msme(payload: MsmeComputeRequest) -> dict[str, Any]:
    return {
        "status": "stub",
        "right_id": "R-007",
        "mode": "demo",
        "stamp": "UNVERIFIED RULE",
        "amount_paise": payload.amount_paise,
        "illustrative": True,
        "trace": [],
        "note": "MSMED dates and interest are not computed until T1/T3 verification.",
    }


@app.get("/v1/unclaimed/guide")
def unclaimed_guide() -> dict[str, Any]:
    return {
        "status": "stub",
        "mode": "demo",
        "steps": [],
        "note": "T6 guide data is not implemented yet.",
    }


@app.post("/v1/unclaimed/guide")
def unclaimed_guide_post(payload: GuideRequest) -> dict[str, Any]:
    return {
        "status": "stub",
        "mode": "demo",
        "asset_types": payload.asset_types,
        "claimant_is_heir": payload.claimant_is_heir,
        "steps": [],
        "note": "No portal automation or identity matching is performed.",
    }


@app.post("/v1/claims/draft")
def claims_draft(payload: ClaimDraftRequest) -> dict[str, Any]:
    return {
        "status": "stub",
        "mode": "demo",
        "stamp": "UNVERIFIED RULE",
        "draft": f"T0 placeholder for {payload.right_id}; user review required.",
        "evidence_checklist": [],
        "escalation_ladder": [],
        "note": "No filing is performed on a user's behalf.",
    }
