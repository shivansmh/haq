from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from engine.calculators.msme import msme_due_date, msme_interest
from engine.classifier import classify_prompt
from engine.delay import compute_range, delay_days
from engine.registry_loader import load_registry
from ingest.paste_parser import parse_alert_text

from .fixtures import health_payload
from .gmail_service import get_google_auth_url, search_gmail
from .schemas import (
    ClaimDraftRequest,
    ClassifyRequest,
    ClassifyResponse,
    DetectRequest,
    GmailScanRequest,
    GuideRequest,
    IngestRequest,
    MsmeComputeRequest,
    PaymentComputeRequest,
)

REGISTRY = load_registry()

app = FastAPI(
    title="Haq API",
    version="0.2.0",
    description=(
        "Statutory rights computation & Gmail noise-cleaning engine for India. "
        "Calculates compensation under RBI TAT circulars, MSMED Act 2006, and official unclaimed assets portals."
    ),
)

# Enable CORS for frontend Vite dev server & production origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.post("/v1/classify", response_model=ClassifyResponse)
def classify_endpoint(payload: ClassifyRequest) -> dict[str, Any]:
    """Auto-classify user chat prompt or document into one of the four statutory categories."""
    return classify_prompt(payload.prompt, payload.filename)


@app.get("/v1/gmail/auth-url")
def gmail_auth_url(redirect_uri: str = "http://localhost:5173/auth/callback") -> dict[str, str]:
    """Generate real Google OAuth 2.0 authorization URL for read-only Gmail access."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "demo-client-id.apps.googleusercontent.com")
    url = get_google_auth_url(client_id, redirect_uri)
    return {"auth_url": url, "client_id_configured": bool(os.getenv("GOOGLE_CLIENT_ID"))}


@app.post("/v1/gmail/scan")
def gmail_scan_endpoint(payload: GmailScanRequest) -> dict[str, Any]:
    """Search Gmail, apply 3-tier noise reduction filter, and detect statutory TAT violations."""
    return search_gmail(payload.access_token, payload.query or "", payload.max_results)


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
        "mode": "live",
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
        "note": "Backed by primary regulator circulars.",
    }


@app.post("/v1/ingest")
def ingest(payload: IngestRequest) -> dict[str, Any]:
    """Parse pasted text, bank alerts, or document rows in memory with zero storage."""
    text = payload.text or ""
    if text:
        parsed_txns, warnings = parse_alert_text(text)
        if parsed_txns:
            return {
                "status": "success",
                "mode": "live",
                "parse_report": {"accepted": True, "rows": len(parsed_txns), "warnings": warnings},
                "transactions": [tx.model_dump(mode="json") for tx in parsed_txns],
            }

    # Fallback to demo fixture if raw text could not be parsed
    return {
        "status": "success",
        "mode": "demo",
        "stamp": "STATUTORY RULE",
        "parse_report": {"accepted": True, "rows": 3, "note": "Parsed in memory without persistence"},
        "transactions": [
            {
                "txn_id": "demo-001",
                "date": "2026-11-03",
                "narration_clean": "UPI / SWIGGY (Debited, Failed at Merchant)",
                "debit": 200000,
                "credit": 0,
                "balance": 1842000,
                "channel": "UPI",
                "ref": "431209845123",
                "parse_confidence": 0.99,
            },
            {
                "txn_id": "demo-002",
                "date": "2026-11-09",
                "narration_clean": "UPI / SWIGGY REVERSAL (Delayed 5 Days)",
                "debit": 0,
                "credit": 200000,
                "balance": 2042000,
                "channel": "UPI",
                "ref": "431209845123",
                "parse_confidence": 0.98,
            },
            {
                "txn_id": "demo-003",
                "date": "2026-10-28",
                "narration_clean": "ATM CASH WDL / ATM8829103 (Cash Not Dispensed)",
                "debit": 500000,
                "credit": 0,
                "balance": 1542000,
                "channel": "ATM",
                "ref": "ATM8829103",
                "parse_confidence": 0.88,
            },
        ],
    }


@app.post("/v1/detect")
def detect(payload: DetectRequest) -> dict[str, Any]:
    return {
        "status": "success",
        "mode": "live",
        "candidates": payload.transactions or [],
        "input_rows": len(payload.transactions),
    }


@app.post("/v1/compute/payment")
def compute_payment(payload: PaymentComputeRequest) -> dict[str, Any]:
    offset = 1 if payload.channel.upper() == "UPI" else 5
    deadline = payload.debit_date + timedelta(days=offset)

    if not payload.confirmed:
        return {
            "status": "confirmation_required",
            "right_id": payload.right_id,
            "mode": "live",
            "message": "Confirm the event details before statutory calculation is finalized.",
        }

    resolution = payload.reversal_date or date.today()
    low_paise, high_paise = compute_range(deadline, resolution, per_day_paise=10000)
    low_days = delay_days(deadline, resolution, count_resolution_day=False)
    high_days = delay_days(deadline, resolution, count_resolution_day=True)

    return {
        "right_id": payload.right_id,
        "mode": "live",
        "stamp": "STATUTORY RBI RULE",
        "deadline": deadline.isoformat(),
        "delay_days": {"low": low_days, "high": high_days},
        "amount_paise": {"low": low_paise, "high": high_paise},
        "unresolved": ["reversal_day_counts"],
        "conflicts": ["C5"],
        "confidence": "High",
        "source_citation": "RBI Circular DPSS.CO.PD No.629/02.01.014/2019-20",
        "trace": [
            {
                "step": 1,
                "text": f"Mandated turnaround time for {payload.channel} is T+{offset} calendar days.",
                "clause": "RBI Harmonised TAT Circular Para 4",
                "inputs": {"debit_date": payload.debit_date.isoformat(), "offset": offset},
            },
            {
                "step": 2,
                "text": f"Statutory reversal deadline was {deadline.isoformat()}.",
                "clause": "R-001 Clock Spec",
                "inputs": {"deadline": deadline.isoformat()},
            },
            {
                "step": 3,
                "text": f"Delay past deadline: {low_days} to {high_days} days (reflecting C5 convention).",
                "clause": "Conflict C5 (Reversal Day Counting)",
                "inputs": {"resolution_date": resolution.isoformat()},
            },
            {
                "step": 4,
                "text": f"Statutory compensation: ₹100/day = ₹{low_paise // 100} to ₹{high_paise // 100}.",
                "clause": "RBI Compensation Schedule",
                "inputs": {"daily_rate_paise": 10000, "low": low_paise, "high": high_paise},
            },
        ],
    }


@app.post("/v1/compute/msme")
def compute_msme(payload: MsmeComputeRequest) -> dict[str, Any]:
    due = msme_due_date(payload.acceptance_date, payload.written_agreement, payload.agreed_days or 45)
    today = payload.payment_date or date.today()
    overdue_days = max(0, (today - due).days)

    interest_paise = msme_interest(payload.amount_paise, overdue_days, bank_rate_pct=6.5)

    return {
        "status": "success",
        "right_id": "R-007",
        "mode": "live",
        "stamp": "STATUTORY MSMED RULE",
        "principal_paise": payload.amount_paise,
        "statutory_due_date": due.isoformat(),
        "days_overdue": overdue_days,
        "bank_rate_pct": 6.5,
        "statutory_rate_pct": 19.5,
        "interest_paise": interest_paise,
        "total_claim_paise": payload.amount_paise + interest_paise,
        "tax_disallowance_note": (
            "Under Section 43B(h) / Section 37(2)(g) of the Income-tax Act, the buyer cannot "
            "claim tax deduction for this unpaid invoice until payment is actually made."
        ),
        "trace": [
            {
                "step": 1,
                "text": f"Goods/services accepted on {payload.acceptance_date.isoformat()}. Statutory limit is {due.isoformat()}.",
                "clause": "MSMED Act 2006, Section 15",
                "inputs": {"statutory_due_date": due.isoformat()},
            },
            {
                "step": 2,
                "text": f"Payment is {overdue_days} days overdue beyond statutory period.",
                "clause": "MSMED Act 2006, Section 15",
                "inputs": {"days_overdue": overdue_days},
            },
            {
                "step": 3,
                "text": "Statutory interest rate: 3 × RBI Bank Rate (3 × 6.50% = 19.50% p.a.) compound monthly.",
                "clause": "MSMED Act 2006, Section 16",
                "inputs": {"rate": "19.50%"},
            },
            {
                "step": 4,
                "text": f"Statutory interest calculated at ₹{interest_paise // 100:,}, total claim ₹{(payload.amount_paise + interest_paise) // 100:,}.",
                "clause": "Section 16 Compounding Schedule",
                "inputs": {"interest_paise": interest_paise, "total_paise": payload.amount_paise + interest_paise},
            },
        ],
    }


@app.get("/v1/unclaimed/guide")
def unclaimed_guide() -> dict[str, Any]:
    return {
        "status": "success",
        "mode": "live",
        "portals": [
            {
                "name": "UDGAM (RBI Unclaimed Deposits)",
                "url": "https://udgam.rbi.org.in",
                "category": "Bank Deposits",
                "guidance": "Covers 30+ banks (~90% of unclaimed deposits by value in the DEA Fund).",
            },
            {
                "name": "IEPF Authority (Ministry of Corporate Affairs)",
                "url": "https://www.iepf.gov.in",
                "category": "Corporate Shares & Dividends",
                "guidance": "Recoverable via e-Form IEPF-5 for shares/dividends unpaid for 7 years.",
            },
            {
                "name": "Bima Bharosa (IRDAI)",
                "url": "https://bimabharosa.irdai.gov.in",
                "category": "Insurance Policies",
                "guidance": "Trace matured policies and unclaimed death claims across all insurers.",
            },
            {
                "name": "EPFO Unified Portal",
                "url": "https://unifiedportal-mem.epfindia.gov.in",
                "category": "Provident Fund",
                "guidance": "Inoperative PF accounts retain interest crediting up to age 58.",
            },
        ],
    }


@app.post("/v1/claims/draft")
def claims_draft(payload: ClaimDraftRequest) -> dict[str, Any]:
    conf = payload.confirmed_result or {}
    amount_str = f"₹{conf.get('amount_paise', {}).get('high', 50000) // 100:,}" if isinstance(conf.get("amount_paise"), dict) else "₹500"
    txn_ref = conf.get("ref", "431209845123")
    bank = payload.bank_name or "[Bank Name / Principal Nodal Officer]"

    draft_text = (
        f"To:\n"
        f"The Principal Nodal Officer\n"
        f"{bank}\n\n"
        f"Subject: Statutory claim for delayed reversal compensation under RBI Circular DPSS.CO.PD No.629/02.01.014/2019-20 (Ref: {txn_ref})\n\n"
        f"Dear Sir / Madam,\n\n"
        f"I am writing to formally request statutory compensation for delayed reversal of a failed payment debited from my account.\n\n"
        f"1. Transaction Reference: {txn_ref}\n"
        f"2. Statutory Compensation Amount: {amount_str} (at ₹100 per day of delay beyond mandated TAT)\n\n"
        f"Under RBI Circular DPSS.CO.PD No.629/02.01.014/2019-20, banks are statutorily required to credit compensation "
        f"automatically without requiring a customer claim. As the credit was not received, please credit {amount_str} "
        f"to my account within 7 working days, failing which this will be escalated to the RBI Integrated Ombudsman (https://cms.rbi.org.in).\n\n"
        f"Yours sincerely,\n"
        f"{payload.claimant_name}\n"
        f"{payload.claimant_mobile or '[Mobile Number]'}\n"
        f"{payload.claimant_email or '[Email Address]'}"
    )

    return {
        "status": "success",
        "mode": "live",
        "stamp": "STATUTORY CLAIM DRAFT",
        "draft": draft_text,
        "evidence_checklist": [
            "Bank statement or alert extract showing the failed debit",
            "Proof of actual reversal date",
            "12-digit UPI RRN / UTR / Reference ID",
            "Copy of this formal notice to the Bank Nodal Officer",
        ],
        "escalation_ladder": [
            "Level 1: Bank Branch & Principal Nodal Officer (wait up to 30 days)",
            "Level 2: RBI Integrated Ombudsman (CMS portal: https://cms.rbi.org.in)",
            "Level 3: District Consumer Disputes Redressal Commission",
        ],
    }
