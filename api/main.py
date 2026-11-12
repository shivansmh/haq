from __future__ import annotations

import math
import os
import secrets
import time
from datetime import date, timedelta
from threading import Lock
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from engine.calculators.msme import msme_due_date
from engine.classifier import classify_prompt
from engine.delay import compute_range, delay_days
from engine.registry_loader import load_registry
from ingest.paste_parser import parse_alert_text
from llm.config import LLMSettings, load_settings
from llm.groq_client import PRICING, GroqClient

from .fixtures import health_payload
from .gmail_service import (
    GmailAccessError,
    exchange_code_for_tokens,
    get_google_auth_url,
    refresh_access_token,
    search_gmail,
)
from .schemas import (
    ClaimDraftRequest,
    ClassifyRequest,
    ClassifyResponse,
    DetectRequest,
    GmailScanRequest,
    GmailSweepRequest,
    IngestRequest,
    MsmeComputeRequest,
    PaymentComputeRequest,
)
from .sweep_jobs import SWEEP_JOBS, SweepJob

REGISTRY = load_registry()
FRONTEND_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,https://shivansmh.github.io").split(",")
    if origin.strip()
]
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://shivansmh.github.io/haq").rstrip("/")
OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/v1/gmail/callback")
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
SESSION_COOKIE = "haq_session"
SESSION_TTL_SECONDS = 3600
OAUTH_STATES: dict[str, dict[str, float | str]] = {}
GMAIL_SESSIONS: dict[str, dict[str, Any]] = {}
GMAIL_HANDOFFS: dict[str, dict[str, float | str]] = {}
GMAIL_HANDOFF_TTL_SECONDS = 300
_GROQ_CLIENT: GroqClient | None = None
_GROQ_CLIENT_LOCK = Lock()


def _frontend_sweep_url() -> str:
    """Return the route that can consume the Gmail-connected callback."""
    if FRONTEND_URL.endswith("/dashboard/sweep"):
        return FRONTEND_URL
    return f"{FRONTEND_URL}/dashboard/sweep"

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
    allow_origins=FRONTEND_ORIGINS,
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


def _session_id(request: Request) -> str | None:
    # GitHub Pages and Render are different sites. Browsers that block
    # third-party cookies need the opaque browser credential issued after OAuth.
    browser_token = request.headers.get("x-haq-session", "").strip()
    if browser_token:
        for session_id, session in GMAIL_SESSIONS.items():
            if secrets.compare_digest(str(session.get("browser_token", "")), browser_token):
                return session_id
    return request.cookies.get(SESSION_COOKIE)


def _set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="none" if COOKIE_SECURE else "lax",
        max_age=SESSION_TTL_SECONDS,
    )


def _gmail_token(request: Request) -> str:
    session_id = _session_id(request)
    session = GMAIL_SESSIONS.get(session_id or "")
    if not session:
        raise HTTPException(status_code=401, detail="Connect Gmail before starting a sweep")
    now = time.time()
    if (
        now - float(session.get("created_at", now)) > SESSION_TTL_SECONDS
        or now - float(session.get("last_seen", now)) > SESSION_TTL_SECONDS
    ):
        GMAIL_SESSIONS.pop(session_id or "", None)
        raise HTTPException(status_code=401, detail="Gmail session expired; connect again")
    session["last_seen"] = now
    if float(session.get("expires_at", 0)) <= time.time() + 60:
        refresh_token = session.get("refresh_token")
        if not refresh_token:
            GMAIL_SESSIONS.pop(session_id or "", None)
            raise HTTPException(status_code=401, detail="Gmail session expired; connect again")
        refreshed = refresh_access_token(
            refresh_token,
            os.getenv("GOOGLE_CLIENT_ID", ""),
            os.getenv("GOOGLE_CLIENT_SECRET", ""),
        )
        if refreshed.get("error") or not refreshed.get("access_token"):
            GMAIL_SESSIONS.pop(session_id or "", None)
            raise HTTPException(status_code=401, detail="Gmail session could not be refreshed")
        session.update(refreshed)
        session["expires_at"] = time.time() + int(refreshed.get("expires_in", 3600))
    return str(session["access_token"])


def _gmail_llm_runtime() -> tuple[GroqClient | None, LLMSettings]:
    """Return optional Groq assistance; the spend ceiling applies per process."""
    global _GROQ_CLIENT
    try:
        settings = load_settings()
    except ValueError:
        # A broken optional provider configuration must never take down Gmail's
        # deterministic-only sweep path; /healthz exposes a safe readiness code.
        return None, LLMSettings()
    if not settings.enabled:
        return None, settings
    with _GROQ_CLIENT_LOCK:
        if _GROQ_CLIENT is None:
            _GROQ_CLIENT = GroqClient(
                api_key=settings.api_key,
                triage_model=settings.triage_model,
                extract_model=settings.extract_model,
                recheck_model=settings.recheck_model,
                timeout_seconds=settings.timeout_seconds,
                spend_cap_usd=settings.spend_cap_usd,
            )
    return _GROQ_CLIENT, settings


def _groq_readiness() -> str:
    enabled = os.getenv("LLM_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    if not enabled:
        return "disabled"
    if not os.getenv("GROQ_API_KEY", "").strip():
        return "missing_key"
    try:
        cap = float(os.getenv("GROQ_SPEND_CAP_USD", "0"))
    except ValueError:
        return "invalid_spend_cap"
    if not math.isfinite(cap) or cap < 0:
        return "invalid_spend_cap"
    if cap == 0:
        return "zero_spend_cap"
    model_ids = (
        os.getenv("LLM_MODEL_TRIAGE", "openai/gpt-oss-20b").strip(),
        os.getenv("LLM_MODEL_EXTRACT", "openai/gpt-oss-20b").strip(),
        os.getenv("LLM_MODEL_RECHECK", "openai/gpt-oss-20b").strip(),
    )
    if any(model not in PRICING for model in model_ids):
        return "unsupported_model"
    return "ready"


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    payload = health_payload()
    payload["groq_status"] = _groq_readiness()
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
def gmail_auth_url(request: Request, response: Response) -> dict[str, str | bool]:
    """Create a CSRF-bound Google consent URL; tokens never go to the browser."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id or not os.getenv("GOOGLE_CLIENT_SECRET"):
        return {"auth_url": "", "client_id_configured": False}
    session_id = _session_id(request) or secrets.token_urlsafe(32)
    state = secrets.token_urlsafe(32)
    OAUTH_STATES[state] = {"session_id": session_id, "created_at": time.time()}
    _set_session_cookie(response, session_id)
    return {
        "auth_url": get_google_auth_url(client_id, OAUTH_REDIRECT_URI, state),
        "client_id_configured": True,
    }


@app.get("/v1/gmail/callback")
def gmail_callback(
    code: str | None = None, state: str | None = None, error: str | None = None
) -> Response:
    """Exchange Google's authorization code server-side and return to the Pages app."""
    state_data = OAUTH_STATES.pop(state or "", None)
    if not state_data or time.time() - float(state_data["created_at"]) > 600:
        return RedirectResponse(f"{_frontend_sweep_url()}?gmail=error&reason=invalid_state", status_code=303)
    if error or not code:
        return RedirectResponse(f"{_frontend_sweep_url()}?gmail=denied", status_code=303)
    tokens = exchange_code_for_tokens(
        code,
        os.getenv("GOOGLE_CLIENT_ID", ""),
        os.getenv("GOOGLE_CLIENT_SECRET", ""),
        OAUTH_REDIRECT_URI,
    )
    if tokens.get("error") or not tokens.get("access_token"):
        return RedirectResponse(f"{_frontend_sweep_url()}?gmail=error&reason=token_exchange", status_code=303)
    session_id = str(state_data["session_id"])
    browser_token = secrets.token_urlsafe(32)
    GMAIL_SESSIONS[session_id] = {
        **tokens,
        "browser_token": browser_token,
        "created_at": time.time(),
        "last_seen": time.time(),
        "expires_at": time.time() + int(tokens.get("expires_in", 3600)),
    }
    handoff = secrets.token_urlsafe(32)
    GMAIL_HANDOFFS[handoff] = {
        "session_id": session_id,
        "created_at": time.time(),
    }
    response = RedirectResponse(f"{_frontend_sweep_url()}?gmail=connected&handoff={handoff}", status_code=303)
    _set_session_cookie(response, session_id)
    return response


@app.post("/v1/gmail/handoff")
def gmail_handoff(payload: dict[str, str]) -> dict[str, str]:
    """Exchange a short-lived OAuth redirect handoff for an opaque Haq session token."""
    handoff = str(payload.get("handoff", "")).strip()
    handoff_data = GMAIL_HANDOFFS.pop(handoff, None)
    if not handoff_data or time.time() - float(handoff_data["created_at"]) > GMAIL_HANDOFF_TTL_SECONDS:
        raise HTTPException(status_code=401, detail="Gmail connection handoff expired; connect again")
    session = GMAIL_SESSIONS.get(str(handoff_data["session_id"]))
    if not session or not session.get("browser_token"):
        raise HTTPException(status_code=401, detail="Gmail session is unavailable; connect again")
    return {"session_token": str(session["browser_token"])}


@app.get("/v1/gmail/status")
def gmail_status(request: Request) -> dict[str, bool]:
    """Report connection state without returning Google tokens or email content."""
    session_id = _session_id(request)
    session = GMAIL_SESSIONS.get(session_id or "")
    if not session:
        return {"connected": False}
    now = time.time()
    if now - float(session.get("created_at", now)) > SESSION_TTL_SECONDS or now - float(session.get("last_seen", now)) > SESSION_TTL_SECONDS:
        GMAIL_SESSIONS.pop(session_id or "", None)
        return {"connected": False}
    session["last_seen"] = now
    return {"connected": True}


@app.post("/v1/gmail/scan")
def gmail_scan_endpoint(request: Request, payload: GmailScanRequest) -> dict[str, Any]:
    """Search Gmail with the server-side session and apply the in-memory sweep."""
    try:
        access_token = _gmail_token(request)
        llm_client, llm_settings = _gmail_llm_runtime()
        return search_gmail(
            access_token,
            payload.query or "",
            payload.max_results,
            llm_client=llm_client,
            llm_settings=llm_settings,
        )
    except GmailAccessError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/v1/gmail/sweeps", status_code=202)
def gmail_sweep_start(request: Request, payload: GmailSweepRequest) -> dict[str, Any]:
    """Start a bounded Gmail sweep without holding the browser request open."""
    session_id = _session_id(request)
    if not session_id:
        raise HTTPException(status_code=401, detail="Connect Gmail before starting a sweep")
    access_token = _gmail_token(request)
    llm_client, llm_settings = _gmail_llm_runtime()

    def worker(job: SweepJob) -> dict[str, Any]:
        def on_progress(**counts: Any) -> None:
            for name in ("listed", "triaged", "analysed", "stage", "truncated"):
                if name in counts:
                    setattr(job, name, counts[name])
            job.updated_at = time.time()

        job.stage = "listing"
        result = search_gmail(
            access_token,
            payload.query or "",
            payload.max_results,
            llm_client=llm_client,
            llm_settings=llm_settings,
            progress=on_progress,
            should_cancel=job.cancel_event.is_set,
        )
        emails = result.get("emails", [])
        job.listed = job.triaged = job.analysed = int(result.get("emails_scanned", 0))
        job.relevant = int(result.get("financial_alerts_found", 0))
        # Honest coverage: only flagged messages the AI cap skipped, never "max_results - analysed".
        job.not_analysed = (
            sum(email["status"] != "noise" and "llm_assistance" not in email for email in emails)
            if llm_client is not None
            else 0
        )
        job.stage = "done"
        job.updated_at = time.time()
        return result

    try:
        job = SWEEP_JOBS.start(session_id, worker)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return job.snapshot()


@app.get("/v1/gmail/sweeps/{job_id}")
def gmail_sweep_status(request: Request, job_id: str) -> dict[str, Any]:
    session_id = _session_id(request)
    job = SWEEP_JOBS.get(job_id, session_id or "")
    if not job:
        raise HTTPException(status_code=404, detail="Sweep job not found or expired")
    return job.snapshot()


@app.delete("/v1/gmail/sweeps/{job_id}")
def gmail_sweep_cancel(request: Request, job_id: str) -> dict[str, Any]:
    session_id = _session_id(request)
    job = SWEEP_JOBS.cancel(job_id, session_id or "")
    if not job:
        raise HTTPException(status_code=404, detail="Sweep job not found or expired")
    return job.snapshot()


@app.post("/v1/gmail/demo")
def gmail_demo() -> dict[str, Any]:
    """Run the synthetic inbox demo without requesting Google access."""
    return search_gmail(None, max_results=50, demo=True)


@app.post("/v1/gmail/disconnect")
def gmail_disconnect(request: Request, response: Response) -> dict[str, bool]:
    """Revoke the Google credential and clear the Haq session cookie."""
    session_id = _session_id(request)
    session = GMAIL_SESSIONS.pop(session_id or "", None)
    if session and session.get("access_token"):
        try:
            import urllib.request

            revoke_payload = urllib.parse.urlencode({"token": str(session["access_token"])}).encode("utf-8")
            revoke_request = urllib.request.Request(
                "https://oauth2.googleapis.com/revoke",
                data=revoke_payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )
            urllib.request.urlopen(revoke_request, timeout=8)
        except Exception:
            pass
    response.delete_cookie(SESSION_COOKIE)
    return {"disconnected": True}


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
    if text.strip().lower() == "synthetic demo":
        return {
            "status": "stub",
            "mode": "demo",
            "stamp": "UNVERIFIED RULE",
            "parse_report": {"accepted": False, "reason": "Synthetic fixture only"},
            "transactions": [],
        }
    if text:
        parsed_txns, warnings = parse_alert_text(text)
        if parsed_txns:
            return {
                "status": "success",
                "mode": "live",
                "parse_report": {"accepted": True, "rows": len(parsed_txns), "warnings": warnings},
                "transactions": [tx.model_dump(mode="json") for tx in parsed_txns],
            }

    return {
        "status": "unparseable",
        "mode": "live",
        "stamp": "UNVERIFIED RULE",
        "parse_report": {
            "accepted": False,
            "rows": 0,
            "reason": "No supported transaction pattern was found in the supplied text.",
        },
        "transactions": [],
    }


@app.post("/v1/detect")
def detect(payload: DetectRequest) -> dict[str, Any]:
    return {
        "status": "stub",
        "mode": "demo",
        "candidates": payload.transactions or [],
        "input_rows": len(payload.transactions),
    }


@app.post("/v1/compute/payment")
def compute_payment(payload: PaymentComputeRequest) -> dict[str, Any]:
    registry_entry = REGISTRY.get(payload.right_id)
    if payload.mode == "live" and registry_entry.status != "Verified":
        raise HTTPException(
            status_code=409,
            detail=f"{payload.right_id} is {registry_entry.status}; live computation is blocked until verification.",
        )
    offset = registry_entry.clock.offset
    daily_rate_paise = registry_entry.amount.parameters.get("daily_rate_paise")
    if offset is None or not isinstance(daily_rate_paise, int) or daily_rate_paise <= 0:
        raise HTTPException(status_code=409, detail="The registry entry lacks a verified clock or amount rule.")
    deadline = payload.debit_date + timedelta(days=offset)

    if not payload.confirmed:
        return {
            "status": "confirmation_required",
            "right_id": payload.right_id,
            "mode": payload.mode,
            "message": "Confirm the event details before statutory calculation is finalized.",
        }

    if payload.reversal_date is None:
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
            "evidence_status": "missing_reversal_date",
            "trace": [],
        }

    resolution = payload.reversal_date
    low_paise, high_paise = compute_range(
        deadline, resolution, per_day_paise=daily_rate_paise
    )
    low_days = delay_days(deadline, resolution, count_resolution_day=False)
    high_days = delay_days(deadline, resolution, count_resolution_day=True)
    verified = registry_entry.status == "Verified" and not registry_entry.unresolved_fields()

    return {
        "right_id": payload.right_id,
        "mode": payload.mode,
        "stamp": "VERIFIED RULE" if verified and payload.mode == "live" else "UNVERIFIED RULE",
        "illustrative": payload.mode == "demo" or not verified,
        "deadline": deadline.isoformat(),
        "delay_days": {"low": low_days, "high": high_days},
        "amount_paise": {"low": low_paise, "high": high_paise},
        "unresolved": ["reversal_day_counts"],
        "conflicts": ["C5"],
        "confidence": registry_entry.confidence if verified and payload.mode == "live" else "Low",
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
                "text": (
                    f"Registry amount rule: ₹{daily_rate_paise // 100}/day = "
                    f"₹{low_paise // 100} to ₹{high_paise // 100}."
                ),
                "clause": "RBI Compensation Schedule",
                "inputs": {"daily_rate_paise": 10000, "low": low_paise, "high": high_paise},
            },
        ],
    }


@app.post("/v1/compute/msme")
def compute_msme(payload: MsmeComputeRequest) -> dict[str, Any]:
    registry_entry = REGISTRY.get("R-007")
    if payload.mode == "live" and registry_entry.status != "Verified":
        raise HTTPException(
            status_code=409,
            detail="R-007 is Seeded; live MSME computation is blocked until verification.",
        )
    due = msme_due_date(payload.acceptance_date, payload.written_agreement, payload.agreed_days or 45)
    today = payload.payment_date or date.today()
    overdue_days = max(0, (today - due).days)

    return {
        "status": "success",
        "right_id": "R-007",
        "mode": payload.mode,
        "stamp": "UNVERIFIED RULE",
        "illustrative": True,
        "principal_paise": payload.amount_paise,
        "statutory_due_date": due.isoformat(),
        "days_overdue": overdue_days,
        "bank_rate_pct": None,
        "statutory_rate_pct": None,
        "interest_paise": None,
        "total_claim_paise": None,
        "tax_disallowance_note": "The registry does not yet contain a verified interest-rate or tax treatment rule.",
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
                "text": "The registry does not contain a verified interest computation for this entry.",
                "clause": "R-007 verification gate",
                "inputs": {},
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
    amount_value = (
        conf.get("amount_paise", {}).get("high")
        if isinstance(conf.get("amount_paise"), dict)
        else None
    )
    amount_str = f"₹{amount_value // 100:,}" if isinstance(amount_value, int) else "[amount to verify]"
    txn_ref = conf.get("ref") or "[transaction reference to verify]"
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
        f"Please review the applicable RBI turnaround-time guidance and confirm whether compensation is due. "
        f"The amount shown above is a working figure, not a legal determination. If unresolved, I may escalate "
        f"through the RBI Integrated Ombudsman (https://cms.rbi.org.in).\n\n"
        f"Yours sincerely,\n"
        f"{payload.claimant_name}\n"
        f"{payload.claimant_mobile or '[Mobile Number]'}\n"
        f"{payload.claimant_email or '[Email Address]'}"
    )

    return {
        "status": "success",
        "mode": "live",
        "stamp": "UNVERIFIED RULE",
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
