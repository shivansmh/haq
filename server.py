"""Haq Zero-Dependency Standalone API Server.

Runs directly on any standard Python 3.10+ without requiring external pip packages.
Exposes all core endpoints:
- POST /v1/classify: Intent auto-classification and entity extraction
- POST /v1/gmail/scan: Real Gmail API sweep, 3-tier noise filter, and violation detection
- GET  /v1/gmail/auth-url: Google OAuth 2.0 authorization URL
- POST /v1/gmail/exchange-token: Exchange OAuth code for access token
- POST /v1/compute/payment: RBI TAT delay and statutory compensation
- POST /v1/compute/msme: MSMED Act Sec 15 & 16 compound interest (3x Bank Rate)
- GET  /v1/unclaimed/guide: Official portals for unclaimed assets
- POST /v1/claims/draft: Ready-to-file legal complaint letter
"""

from __future__ import annotations

import json
import os
import urllib.parse
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

from api.gmail_service import (
    exchange_code_for_tokens,
    get_google_auth_url,
    search_gmail,
)
from engine.calculators.msme import msme_due_date, msme_interest
from engine.classifier import classify_prompt
from engine.delay import compute_range, delay_days


class HaqRequestHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, x-request-id")

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def _send_json(self, status_code: int, data: dict) -> None:
        payload = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status_code)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_json_body(self) -> dict:
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len == 0:
            return {}
        raw = self.rfile.read(content_len).decode("utf-8")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/healthz":
            self._send_json(200, {"status": "ok", "mode": "live", "service": "haq-api", "version": "0.3.0"})
        elif path == "/v1/gmail/auth-url":
            client_id = os.getenv("GOOGLE_CLIENT_ID", "48291029384-haq-demo.apps.googleusercontent.com")
            redirect_uri = "http://localhost:5173/auth/callback"
            url = get_google_auth_url(client_id, redirect_uri)
            self._send_json(200, {
                "auth_url": url,
                "client_id": client_id,
                "client_id_configured": bool(os.getenv("GOOGLE_CLIENT_ID")),
                "scope": "https://www.googleapis.com/auth/gmail.readonly",
            })
        elif path == "/v1/unclaimed/guide":
            self._send_json(200, {
                "status": "success",
                "portals": [
                    {"name": "UDGAM (RBI)", "url": "https://udgam.rbi.org.in", "category": "Bank Deposits"},
                    {"name": "IEPF (MCA)", "url": "https://www.iepf.gov.in", "category": "Shares & Dividends"},
                    {"name": "Bima Bharosa (IRDAI)", "url": "https://bimabharosa.irdai.gov.in", "category": "Insurance"},
                    {"name": "EPFO Unified Portal", "url": "https://unifiedportal-mem.epfindia.gov.in", "category": "Provident Fund"},
                ],
            })
        else:
            self._send_json(404, {"error": "Not found", "path": path})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

        if path == "/v1/classify":
            prompt = body.get("prompt", "")
            filename = body.get("filename")
            result = classify_prompt(prompt, filename)
            self._send_json(200, result)

        elif path == "/v1/gmail/scan":
            token = body.get("access_token")
            # Also check Authorization header if passed
            auth_header = self.headers.get("Authorization", "")
            if not token and auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "").strip()

            query = body.get("query", "")
            max_res = body.get("max_results", 50)
            result = search_gmail(token, query, max_res)
            self._send_json(200, result)

        elif path == "/v1/gmail/exchange-token":
            code = body.get("code", "")
            client_id = body.get("client_id") or os.getenv("GOOGLE_CLIENT_ID", "")
            client_secret = body.get("client_secret") or os.getenv("GOOGLE_CLIENT_SECRET", "")
            redirect_uri = body.get("redirect_uri", "http://localhost:5173/auth/callback")

            tokens = exchange_code_for_tokens(code, client_id, client_secret, redirect_uri)
            self._send_json(200, tokens)

        elif path == "/v1/compute/payment":
            channel = body.get("channel", "UPI")
            offset = 1 if channel.upper() == "UPI" else 5
            try:
                debit_d = date.fromisoformat(body.get("debit_date", "2026-11-03"))
            except ValueError:
                debit_d = date(2026, 11, 3)

            deadline = debit_d + timedelta(days=offset)
            try:
                resol_d = date.fromisoformat(body.get("reversal_date", "2026-11-09"))
            except ValueError:
                resol_d = date(2026, 11, 9)

            low_paise, high_paise = compute_range(deadline, resol_d, per_day_paise=10000)
            low_days = delay_days(deadline, resol_d, count_resolution_day=False)
            high_days = delay_days(deadline, resol_d, count_resolution_day=True)

            self._send_json(200, {
                "right_id": body.get("right_id", "R-001"),
                "mode": "live",
                "stamp": "STATUTORY RBI RULE",
                "deadline": deadline.isoformat(),
                "delay_days": {"low": low_days, "high": high_days},
                "amount_paise": {"low": low_paise, "high": high_paise},
                "confidence": "High",
                "source_citation": "RBI Circular DPSS.CO.PD No.629/02.01.014/2019-20",
                "trace": [
                    {"step": 1, "text": f"Mandated turnaround time for {channel} is T+{offset} days.", "clause": "RBI Circular Para 4"},
                    {"step": 2, "text": f"Statutory reversal deadline was {deadline.isoformat()}.", "clause": "Clock Spec"},
                    {"step": 3, "text": f"Delay past deadline: {low_days} to {high_days} days (reflecting C5 convention).", "clause": "Conflict C5"},
                    {"step": 4, "text": f"Statutory compensation: ₹100/day = ₹{low_paise // 100} to ₹{high_paise // 100}.", "clause": "RBI Schedule"},
                ],
            })

        elif path == "/v1/compute/msme":
            try:
                acc_d = date.fromisoformat(body.get("acceptance_date", "2026-09-01"))
            except ValueError:
                acc_d = date(2026, 9, 1)

            has_agr = bool(body.get("written_agreement", True))
            agreed_days = int(body.get("agreed_days", 45))
            amount_paise = int(body.get("amount_paise", 14280000))

            due = msme_due_date(acc_d, has_agr, agreed_days)
            today = date.today()
            overdue_days = max(0, (today - due).days)
            interest_paise = msme_interest(amount_paise, overdue_days, bank_rate_pct=6.5)

            self._send_json(200, {
                "status": "success",
                "statutory_due_date": due.isoformat(),
                "days_overdue": overdue_days,
                "bank_rate_pct": 6.5,
                "statutory_rate_pct": 19.5,
                "interest_paise": interest_paise,
                "total_claim_paise": amount_paise + interest_paise,
                "tax_disallowance_note": "Buyer deduction disallowed under Section 43B(h) / Section 37(2)(g).",
            })

        elif path == "/v1/claims/draft":
            txn_ref = body.get("confirmed_result", {}).get("ref", "431209845123")
            draft_text = (
                f"To:\nThe Principal Nodal Officer\nCustomer Service Department\n[Bank Name]\n\n"
                f"Subject: Statutory claim for delayed reversal compensation under RBI Circular DPSS.CO.PD No.629 (Ref: {txn_ref})\n\n"
                f"Dear Sir/Madam,\n\nI request statutory compensation for delayed reversal of a failed payment of ₹2,000.\n"
                f"Under RBI Circular DPSS.CO.PD No.629/02.01.014/2019-20, compensation at ₹100/day is payable automatically. "
                f"Please credit this within 7 working days, failing which this will be escalated to the RBI Ombudsman.\n\n"
                f"Yours sincerely,\n[Claimant Name]"
            )
            self._send_json(200, {
                "status": "success",
                "draft": draft_text,
                "evidence_checklist": ["Bank statement showing debit", "Proof of reversal date", "12-digit UPI RRN / UTR"],
                "escalation_ladder": ["Level 1: Bank Nodal Officer", "Level 2: RBI Integrated Ombudsman (CMS)"],
            })

        else:
            self._send_json(404, {"error": "Not found", "path": path})


def run_server(port: int = 8000) -> None:
    server_address = ("127.0.0.1", port)
    httpd = HTTPServer(server_address, HaqRequestHandler)
    print(f"Haq backend server running on http://127.0.0.1:{port}")
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()
