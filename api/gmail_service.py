"""Haq Gmail Service: Production-Grade Gmail Sweep & Noise Reduction Engine.

Inspired by the Airfairness Sweep architecture:
1. Explicit user consent and Google OAuth 2.0 authentication.
2. Restricted, read-only Gmail access (`https://www.googleapis.com/auth/gmail.readonly`).
3. Real-time REST API integration with `https://gmail.googleapis.com/gmail/v1/users/me/messages`.
4. Multi-part body decoding (Base64url), header parsing, and entity extraction.
5. Smart 3-Tier Financial Noise Cleaner:
   - Strips OTPs, promotional newsletters, marketing campaigns, and shipping updates.
   - Isolates verified debit alerts and reversal notices from Indian banks & FinTech apps.
   - Pairs debits with delayed or missing credits to compute statutory turnaround-time penalties (RBI TAT Circular).
6. Ephemeral transient processing: zero permanent storage of email bodies or tokens.
7. High-fidelity demo corpus fallback for offline testing and stage presentations.
"""

from __future__ import annotations

import base64
import json
import re
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError

from cases.builder import build_cases
from claims.pack import build_claim_pack
from events.normalize import normalize_emails
from ledger.build import build_flagged_records, project_email
from ledger.summary import summarize_records
from llm.client import LLMClient
from llm.config import LLMSettings
from llm.gmail_assistance import enrich_financial_emails
from llm.ledger_assist import enrich_flagged_records
from llm.redact import OAuthTokenDetected, redact_sensitive

from .upi_signals import (
    classify_message,
    classify_sender,
    looks_payment_related,
)
from .upi_signals import parse_amount as _parse_amount

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


class GmailAccessError(RuntimeError):
    """Raised when Google refuses or cannot complete a Gmail API request."""

DATE_RE = re.compile(
    r"\b(\d{1,2})[\s/-]+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"[a-z]*[\s,-]+(20\d{2})\b",
    re.IGNORECASE,
)
MAX_QUERY_LENGTH = 1200
MAX_FETCH_RESULTS = 5000
GMAIL_WORKERS = 6  # parallel message reads; well inside Gmail's per-user quota
REVERSAL_MATCH_WINDOW_DAYS = 30

# Narrow server-side query: payment wording only, last 12 months, and known developer or
# social senders excluded so Gmail never even returns them. Looser wording ("failed",
# "payment", "invoice") on its own is what pulled GitHub CI mail into the first sweep.
DEFAULT_GMAIL_QUERY = (
    "newer_than:365d -category:promotions -category:social -category:forums "
    "-from:github.com -from:gitlab.com -from:linkedin.com -from:vercel.com -from:render.com "
    '(upi OR "payment failed" OR "transaction failed" OR "payment unsuccessful" OR debited '
    'OR reversal OR "refund initiated" OR "order cancelled" OR "order canceled" '
    'OR "has been cancelled" OR "could not be processed" OR "cash not dispensed" '
    'OR "in-app purchase" OR "battle pass" OR game OR gaming OR "top up" '
    'OR invoice OR "purchase order" OR "remittance advice" OR overdue '
    "OR विफल OR रिफंड OR रद्द)"
)

ProgressFn = Callable[..., None]


def get_google_auth_url(client_id: str, redirect_uri: str, state: str) -> str:
    """Generate Google OAuth 2.0 authorization URL requesting read-only Gmail access."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GMAIL_SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{GOOGLE_AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(
    code: str, client_id: str, client_secret: str, redirect_uri: str
) -> dict[str, Any]:
    """Exchange authorization code with Google's OAuth token endpoint for access token."""
    payload = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }).encode("utf-8")

    req = urllib.request.Request(
        GOOGLE_TOKEN_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


def refresh_access_token(refresh_token: str, client_id: str, client_secret: str) -> dict[str, Any]:
    """Refresh an access token without exposing the refresh token to the browser."""
    payload = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode("utf-8")
    req = urllib.request.Request(
        GOOGLE_TOKEN_ENDPOINT,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"error": str(exc)}


def decode_base64_url(encoded: str) -> str:
    """Safely decode Base64url formatted string from Gmail API."""
    if not encoded:
        return ""
    try:
        padding = "=" * (4 - (len(encoded) % 4))
        raw = base64.urlsafe_b64decode(encoded + padding)
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""


class _ReadableHTML(HTMLParser):
    """Extract visible email text while dropping markup, styles, and scripts."""

    _SKIP = {"head", "script", "style", "noscript", "svg"}
    _BLOCK = {"address", "article", "blockquote", "br", "div", "footer", "h1", "h2", "h3", "li", "p", "section", "table", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP:
            self._skip_depth += 1
        elif not self._skip_depth and tag in self._BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif not self._skip_depth and tag in self._BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)

    def text(self) -> str:
        rows = [re.sub(r"[ \t\xa0]+", " ", row).strip() for row in "".join(self.parts).splitlines()]
        return "\n".join(row for row in rows if row)


def extract_body_from_payload(payload: dict[str, Any]) -> str:
    """Prefer plain text; otherwise return visible HTML text, bounded for transient use."""
    plain_chunks: list[str] = []
    html_chunks: list[str] = []

    def visit(node: dict[str, Any]) -> None:
        mime = node.get("mimeType", "")
        data = node.get("body", {}).get("data", "")
        if data and mime == "text/plain":
            plain_chunks.append(decode_base64_url(data))
        elif data and mime == "text/html":
            parser = _ReadableHTML()
            parser.feed(decode_base64_url(data))
            parser.close()
            html_chunks.append(parser.text())
        for child in node.get("parts", []):
            visit(child)

    visit(payload)
    chunks = plain_chunks or html_chunks
    return "\n".join(chunk for chunk in chunks if chunk)[:8000]


def parse_message_date(value: str, body: str = "") -> str | None:
    """Return an ISO date from a header or common Indian alert date in the body."""
    if value:
        try:
            return parsedate_to_datetime(value).date().isoformat()
        except (TypeError, ValueError, OverflowError):
            pass
    match = DATE_RE.search(body)
    if match:
        try:
            return datetime.strptime(
                f"{match.group(1)} {match.group(2)} {match.group(3)}", "%d %b %Y"
            ).date().isoformat()
        except ValueError:
            pass
    return None


def parse_amount(text: str) -> int | None:
    return _parse_amount(text)


def _list_message_ids(
    headers: dict[str, str], query: str, max_results: int, report: ProgressFn, cancelled: Callable[[], bool]
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    page_token: str | None = None
    while len(found) < max_results and not cancelled():
        params = {"q": query, "maxResults": str(min(500, max_results - len(found)))}
        if page_token:
            params["pageToken"] = page_token
        url = "https://gmail.googleapis.com/gmail/v1/users/me/messages?" + urllib.parse.urlencode(params)
        data = _gmail_json(urllib.request.Request(url, headers=headers), timeout=12)
        found.extend(data.get("messages", []))
        report(listed=len(found), stage="listing")
        page_token = data.get("nextPageToken")
        if not page_token or not data.get("messages"):
            break
    return found[:max_results]


def _get_message(headers: dict[str, str], msg_id: str, fmt: str) -> dict[str, Any]:
    base = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{urllib.parse.quote(msg_id)}"
    if fmt == "metadata":
        base += "?format=metadata&metadataHeaders=From&metadataHeaders=Subject&metadataHeaders=Date"
    else:
        base += "?format=full"
    return _gmail_json(urllib.request.Request(base, headers=headers), timeout=8)


def _to_record(msg_id: str, msg_data: dict[str, Any], body_text: str = "") -> dict[str, Any]:
    payload = msg_data.get("payload", {})
    message_headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
    return {
        "id": msg_id,
        "sender": message_headers.get("from", "Unknown Sender"),
        "subject": message_headers.get("subject", "No Subject"),
        "date": message_headers.get("date", ""),
        "snippet": msg_data.get("snippet", "") or body_text[:240],
        "body": body_text,
        "is_real": True,
    }


def _read_parallel(
    fetch: Callable[[Any], dict[str, Any]],
    items: list[Any],
    on_done: Callable[[], None],
    cancelled: Callable[[], bool],
) -> list[dict[str, Any] | None]:
    def task(item: Any) -> dict[str, Any] | None:
        if cancelled():
            return None
        try:
            return fetch(item)
        except HTTPError:
            return None  # one unreadable message must not fail the whole sweep

    results: list[dict[str, Any] | None] = []
    with ThreadPoolExecutor(max_workers=GMAIL_WORKERS) as pool:
        for value in pool.map(task, items):
            results.append(value)
            on_done()
    return results


def fetch_live_gmail(
    access_token: str,
    query: str,
    max_results: int = 50,
    *,
    progress: ProgressFn | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> list[dict[str, Any]]:
    """Funnel: list ids -> read headers only -> open bodies only for plausible payment mail.

    Developer/social senders and unknown senders with no payment wording in the subject or
    snippet never have their bodies opened. Progress is reported live through `progress`.
    """
    max_results = min(max_results, MAX_FETCH_RESULTS)
    financial_query = (query or DEFAULT_GMAIL_QUERY).strip()
    if len(financial_query) > MAX_QUERY_LENGTH:
        raise GmailAccessError("Gmail search query is too long")

    def report(**counts: Any) -> None:
        if progress:
            progress(**counts)

    def cancelled() -> bool:
        return bool(should_cancel and should_cancel())

    headers = {"Authorization": f"Bearer {access_token}"}
    try:
        ids = _list_message_ids(headers, financial_query, max_results, report, cancelled)
        report(listed=len(ids), truncated=len(ids) >= max_results, stage="reading headers")

        header_done = 0

        def header_tick() -> None:
            nonlocal header_done
            header_done += 1
            report(triaged=header_done)

        metas = _read_parallel(
            lambda item: _get_message(headers, item["id"], "metadata"), ids, header_tick, cancelled
        )
        records: list[dict[str, Any]] = []
        to_open: list[int] = []
        for item, meta in zip(ids, metas, strict=True):
            if meta is None:
                continue
            record = _to_record(item["id"], meta)
            tier = classify_sender(record["sender"])
            if tier != "blocked" and (tier != "unknown" or looks_payment_related(record["subject"], record["snippet"])):
                to_open.append(len(records))
            records.append(record)

        resolved = len(records) - len(to_open)  # decided from headers alone
        report(analysed=resolved, stage="opening likely payment emails")

        def body_tick() -> None:
            nonlocal resolved
            resolved += 1
            report(analysed=resolved)

        fulls = _read_parallel(
            lambda index: _get_message(headers, records[index]["id"], "full"), to_open, body_tick, cancelled
        )
        for index, full in zip(to_open, fulls, strict=True):
            if full:
                records[index] = _to_record(
                    records[index]["id"], full, extract_body_from_payload(full.get("payload", {}))
                )
        return records
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise GmailAccessError(f"Google Gmail API returned {exc.code}: {detail[:240]}") from exc
    except GmailAccessError:
        raise
    except Exception as exc:
        raise GmailAccessError("Google Gmail API could not be reached") from exc


def _gmail_json(request: urllib.request.Request, *, timeout: float) -> dict[str, Any]:
    """Read one Gmail response, respecting Retry-After for transient quota responses."""
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 3:
                raise
            retry_after = exc.headers.get("Retry-After", "")
            try:
                delay = min(float(retry_after), 8.0) if retry_after else 0.5 * (2**attempt)
            except ValueError:
                delay = 0.5 * (2**attempt)
            time.sleep(max(0.0, delay))
    raise GmailAccessError("Gmail request retry budget exhausted")


def get_demo_email_corpus() -> list[dict[str, Any]]:
    """Comprehensive synthetic inbox reflecting real Indian consumer and business transactions."""
    demo_ref = "UPIREF-DEMO-001"

    def sender(local: str, domain: str) -> str:
        # Keep the shared demo fixture free of mailbox addresses while still
        # exercising sender-domain classification.
        return domain

    return [
        {
            "id": "msg-001",
            "sender": sender("alerts", "hdfcbank.net"),
            "subject": "Alert: Your HDFC Bank account was debited for UPI txn Rs 2,000.00",
            "date": "03 Nov 2026, 14:22",
            "snippet": f"Rs 2,000.00 debited from account **XXXX via UPI to SWIGGY. UPI Ref {demo_ref}. If not done by you, report to bank.",
            "body": f"Dear Customer, Rs 2,000.00 has been debited from your account **XXXX on 03-Nov-2026 towards UPI txn to SWIGGY. UPI Reference Number: {demo_ref}. If this was not authorized by you, contact your bank.",
            "is_real": True,
        },
        {
            "id": "msg-002",
            "sender": sender("support", "phonepe.com"),
            "subject": "Payment Failed: Your payment of Rs 2,000 at Swiggy was not completed",
            "date": "03 Nov 2026, 14:23",
            "snippet": "Your payment failed at merchant end. Amount debited from your bank will be reversed automatically within RBI TAT.",
            "body": "Hi Shivansh, your transaction of Rs 2,000 at Swiggy failed. Since money was debited from your bank account, it will be refunded back as per the RBI turnaround time framework.",
            "is_real": True,
        },
        {
            "id": "msg-003",
            "sender": sender("alerts", "hdfcbank.net"),
            "subject": "Alert: Reversal credit of Rs 2,000.00 received in your account",
            "date": "09 Nov 2026, 11:05",
            "snippet": f"Account **XXXX credited with Rs 2,000.00 on 09-Nov-2026 by UPI Reversal / SWIGGY / {demo_ref}.",
            "body": f"Dear Customer, account **XXXX credited with Rs 2,000.00 on 09-Nov-2026 11:05:12 by UPI Reversal / SWIGGY / {demo_ref}. Available balance: Rs 20,420.00.",
            "is_real": True,
        },
        {
            "id": "msg-004",
            "sender": sender("no-reply", "sbi.co.in"),
            "subject": "Transaction Alert: ATM Cash Dispense Incomplete Rs 5,000.00",
            "date": "28 Oct 2026, 19:40",
            "snippet": "Dear Customer, txn at ATM 9422 failed to dispense cash Rs 5,000. Ref: ATM8829103. If not reversed in 5 days, contact branch.",
            "body": "State Bank Alert: Your card **4412 attempted cash withdrawal of Rs 5,000.00 at ATM S1NW009422. Cash was not dispensed due to terminal timeout. Txn Ref: ATM8829103.",
            "is_real": True,
        },
        {
            "id": "msg-005",
            "sender": sender("accounts", "techbuyer-corp.in"),
            "subject": "Overdue Notice: Payment status for Invoice #MSME-2026-441",
            "date": "15 Oct 2026, 10:30",
            "snippet": "Dear Supplier, regarding your tax invoice #MSME-2026-441 for Rs 1,42,800.00, our finance team is processing approval. Dues are overdue by 42 days.",
            "body": "Dear Shivansh, regarding Invoice #MSME-2026-441 for software development services (amount: Rs 1,42,800.00, acceptance date: 03-Sep-2026), our audit is underway. We acknowledge dues are overdue.",
            "is_real": True,
        },
        {
            "id": "msg-006",
            "sender": sender("promotions", "swiggy.in"),
            "subject": "Craving Biryani? Get 50% flat off on tonight’s feast!",
            "date": "03 Nov 2026, 19:00",
            "snippet": "Use code TASTY50 on orders above Rs 299. Explore top rated restaurants near you now...",
            "body": "Top offers of the day! Use coupon TASTY50 to get flat 50% off on all biryani and dessert orders tonight.",
            "is_real": False,
        },
        {
            "id": "msg-007",
            "sender": sender("accounts-google-com", "google.com"),
            "subject": "Google Verification Code: 482910",
            "date": "04 Nov 2026, 09:12",
            "snippet": "Your one-time verification code is 482910. Never share this code with anyone...",
            "body": "Your Google verification code is 482910. Do not share this OTP with anyone.",
            "is_real": False,
        },
        {
            "id": "msg-008",
            "sender": sender("notifications", "linkedin.com"),
            "subject": "Shivansh, you appeared in 14 searches this week",
            "date": "05 Nov 2026, 10:15",
            "snippet": "See who is looking for skills like Python, AI Agents, and React in your area...",
            "body": "Your weekly profile analytics are ready. 14 people viewed your profile this week.",
            "is_real": False,
        },
        {
            "id": "msg-009",
            "sender": sender("auto-confirm", "amazon.in"),
            "subject": "Delivered: Your package with Noise Cancelling Earphones",
            "date": "06 Nov 2026, 16:30",
            "snippet": "Your order was handed directly to a resident. Let us know how delivery went...",
            "body": "Package delivery confirmation for Order #402-9912039-11203. Handed to customer.",
            "is_real": False,
        },
        # A duplicate bank alert: same ref, amount and date as msg-001. It must fold
        # into the same record instead of becoming a second claim.
        {
            "id": "msg-010",
            "sender": sender("alerts", "hdfcbank.net"),
            "subject": "Alert: Your HDFC Bank account was debited for UPI txn Rs 2,000.00",
            "date": "03 Nov 2026, 14:22",
            "snippet": f"Rs 2,000.00 debited from account **XXXX via UPI to SWIGGY. UPI Ref {demo_ref}.",
            "body": f"Dear Customer, Rs 2,000.00 has been debited from your account **XXXX on 03-Nov-2026 towards UPI txn to SWIGGY. UPI Reference Number: {demo_ref}.",
            "is_real": True,
        },
        # Gaming / in-app purchase path: debit, failed purchase and a refund.
        {
            "id": "msg-011",
            "sender": sender("alerts", "hdfcbank.net"),
            "subject": "Alert: UPI debit of Rs 1,299.00 for STEAM purchase",
            "date": "05 Nov 2026, 21:14",
            "snippet": "Rs 1,299.00 debited via UPI to STEAM. UPI Ref UPIREF-DEMO-002.",
            "body": "Dear Customer, Rs 1,299.00 has been debited from your account **XXXX on 05-Nov-2026 towards UPI txn to STEAM. UPI Reference Number: UPIREF-DEMO-002.",
            "is_real": True,
        },
        {
            "id": "msg-012",
            "sender": sender("support", "steampowered.com"),
            "subject": "Purchase failed: Steam wallet top-up of Rs 1,299",
            "date": "05 Nov 2026, 21:15",
            "snippet": "Your Steam wallet top-up failed. Any debited amount will be reversed.",
            "body": "Your in-app purchase of Rs 1,299 for a Steam wallet top-up failed at the payment provider. The debited amount will be reversed automatically.",
            "is_real": True,
        },
        {
            "id": "msg-013",
            "sender": sender("alerts", "hdfcbank.net"),
            "subject": "Alert: Reversal credit of Rs 1,299.00 received",
            "date": "12 Nov 2026, 09:02",
            "snippet": "Account **XXXX credited with Rs 1,299.00 by UPI Reversal / STEAM / UPIREF-DEMO-002.",
            "body": "Dear Customer, account **XXXX credited with Rs 1,299.00 on 12-Nov-2026 by UPI Reversal / STEAM / UPIREF-DEMO-002.",
            "is_real": True,
        },
        # Business path: the buyer confirms the overdue invoice was paid, so the
        # ledger can close the record and keep the payment evidence.
        {
            "id": "msg-014",
            "sender": sender("accounts", "techbuyer-corp.in"),
            "subject": "Payment received: Invoice #MSME-2026-441",
            "date": "10 Nov 2026, 12:40",
            "snippet": "Remittance advice: payment of Rs 1,42,800.00 for Invoice #MSME-2026-441 has been received.",
            "body": "Dear Shivansh, this is a remittance advice confirming that payment of Rs 1,42,800.00 against Invoice #MSME-2026-441 has been received by our accounts team and settled on 10-Nov-2026.",
            "is_real": True,
        },
    ]


def _safe_display_text(value: Any) -> str:
    try:
        return redact_sensitive(str(value or "")).redacted_text
    except OAuthTokenDetected:
        return "[CREDENTIAL REDACTED]"


def _days_between(earlier: str | None, later: str | None) -> int | None:
    if not earlier or not later:
        return None
    try:
        return (date.fromisoformat(later) - date.fromisoformat(earlier)).days
    except ValueError:
        return None


_NARRATION = {
    "upi_failed_debited": "Payment failed and the message mentions a debit",
    "upi_failed": "Payment failed; debit not confirmed in this message",
    "order_cancelled": "Order cancelled; refund not confirmed in this message",
    "atm_failure": "ATM withdrawal failed",
    "overdue_invoice": "Invoice marked overdue",
    "invoice_paid": "Invoice payment confirmation",
    "debit": "Debit followed by a matching reversal",
}


def filter_and_extract_transactions(
    raw_messages: list[dict[str, Any]],
    *,
    llm_client: LLMClient | None = None,
    llm_settings: LLMSettings | None = None,
) -> dict[str, Any]:
    """Clean a bounded inbox and emit only evidence-derived signals and candidates."""
    audited_emails: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    tier_by_id: dict[str, str] = {}
    signals_by_id: dict[str, Any] = {}

    for msg in raw_messages:
        signal = classify_message(
            msg.get("sender", ""), msg.get("subject", ""), msg.get("snippet", ""), msg.get("body", "")
        )
        signals_by_id[str(msg.get("id", ""))] = signal
        tier_by_id[str(msg.get("id", ""))] = signal.sender_tier
        if signal.is_noise:
            audited_emails.append(
                {**msg, "status": "noise", "filterTag": signal.tag, "signalReasons": list(signal.reasons)}
            )
            continue
        items.append(
            {
                **msg,
                "kind": signal.kind,
                "signal_kind": signal.kind,
                "channel": signal.channel,
                "amount_paise": signal.amount_paise,
                "ref": signal.ref,
                "date_iso": parse_message_date(msg.get("date", ""), msg.get("body", "")),
            }
        )
        audited_emails.append(
            {
                **msg,
                "status": "violation_detected" if signal.is_exception else "financial_alert",
                "filterTag": signal.tag,
                "signalKind": signal.kind,
                "signalReasons": list(signal.reasons),
                "extractedAmount": signal.amount_paise,
                "extractedChannel": signal.channel,
                "extractedRef": signal.ref,
            }
        )

    def source(item: dict[str, Any]) -> dict[str, str]:
        return {
            "sender": _safe_display_text(item.get("sender", "Unknown Sender")),
            "subject": _safe_display_text(item.get("subject", "No Subject")),
            "snippet": _safe_display_text(item.get("snippet", "")),
        }

    refunds = [item for item in items if item["kind"] == "refund_credited"]

    def find_reversal(origin: dict[str, Any]) -> dict[str, Any] | None:
        matches = []
        for refund in refunds:
            gap = _days_between(origin.get("date_iso"), refund.get("date_iso"))
            if gap is None or gap < 0:
                continue
            if origin["ref"] and refund["ref"]:
                same = origin["ref"] == refund["ref"]
            else:  # no reference on one side: fall back to amount inside a short window
                same = (
                    bool(origin["amount_paise"])
                    and origin["amount_paise"] == refund["amount_paise"]
                    and gap <= REVERSAL_MATCH_WINDOW_DAYS
                )
            if same:
                matches.append(refund)
        return min(matches, key=lambda item: item["date_iso"]) if matches else None

    def candidate(item: dict[str, Any], reversal: dict[str, Any] | None) -> dict[str, Any]:
        return {
            "txn_id": f"gmail-{item['id']}",
            "date": item.get("date_iso"),
            "reversal_date": reversal.get("date_iso") if reversal else None,
            "narration_clean": _NARRATION.get(item["kind"], "Payment exception"),
            "debit": item.get("amount_paise") or 0,
            "channel": item["channel"],
            "ref": item.get("ref"),
            "parse_confidence": (0.9 if item.get("date_iso") else 0.7) if reversal
            else (0.75 if item.get("amount_paise") else 0.55),
            "evidence_status": "paired_reversal" if reversal else "potential_exception",
            "reversal_seen": reversal is not None,
            "email_source": source(item),
            "related_sources": [],
        }

    candidates: list[dict[str, Any]] = []
    # 1. A debit alert with a matching reversal: the delay itself is the evidence.
    for debit in (item for item in items if item["kind"] == "debit"):
        reversal = find_reversal(debit)
        if reversal:
            candidates.append(candidate(debit, reversal))

    def already_covered(item: dict[str, Any]) -> dict[str, Any] | None:
        for existing in candidates:
            gap = _days_between(existing["date"], item.get("date_iso"))
            same_amount = existing["debit"] == (item.get("amount_paise") or 0)
            same_ref = not (existing["ref"] and item.get("ref")) or existing["ref"] == item.get("ref")
            if (
                existing["channel"] == item["channel"] and same_amount and same_ref
                and gap is not None and abs(gap) <= 1
            ):
                return existing
        return None

    # 2. Failure / cancellation / overdue messages; merged into (1) when they describe the same payment.
    for item in items:
        if item["kind"] in {"debit", "refund_credited"}:
            continue
        covered = already_covered(item)
        if covered:
            covered["related_sources"].append(source(item))
            continue
        candidates.append(candidate(item, find_reversal(item)))

    safe_emails = [
        {
            **{key: value for key, value in email.items() if key not in {"body", "is_real"}},
            "sender": _safe_display_text(email.get("sender", "Unknown Sender")),
            "subject": _safe_display_text(email.get("subject", "No Subject")),
            "snippet": _safe_display_text(email.get("snippet", "")),
        }
        for email in audited_emails
    ]
    safe_emails, llm_status = enrich_financial_emails(
        raw_messages,
        safe_emails,
        client=llm_client,
        settings=llm_settings or LLMSettings(),
    )

    # The model may only *remove* weak evidence: an unknown-sender candidate that triage calls
    # "possible noise" is dropped. It can never add a candidate or change a deterministic field.
    vetoed: set[str] = set()
    for email in safe_emails:
        relevance = (email.get("llm_assistance") or {}).get("relevance")
        if (
            email["status"] != "noise"
            and relevance == "possible_noise"
            and tier_by_id.get(str(email.get("id", ""))) == "unknown"
        ):
            email.update(status="noise", filterTag="AI reviewed: not a payment event", vetoed_by_ai=True)
            vetoed.add(str(email["id"]))
    candidates = [c for c in candidates if c["txn_id"].removeprefix("gmail-") not in vetoed]

    settings = llm_settings or LLMSettings()
    domain_messages = [
        message for message in raw_messages
        if str(message.get("id", "")) not in vetoed
    ]
    # One classification pass: events reuse the signals computed above instead of
    # re-parsing every subject/body. Cases still group related emails.
    events = normalize_emails(domain_messages, signals_by_id)
    cases = build_cases(events)
    case_payloads = [case.model_dump(mode="json") for case in cases]
    claim_packs = [build_claim_pack(case) for case in cases if case.worth_review or case.status == "open"]

    # A structured record per transaction/invoice, with refund tracking and labels.
    records = build_flagged_records(cases)
    records, ledger_status = enrich_flagged_records(records, client=llm_client, settings=settings)
    record_payloads = [record.model_dump(mode="json") for record in records]
    record_by_email: dict[str, Any] = {}
    for record in records:
        for item in record.evidence:
            record_by_email.setdefault(item.email_id, record)
    for email in safe_emails:
        email_id = str(email.get("id", ""))
        record = record_by_email.get(email_id)
        if record is None:
            email.update(record_id=None, cluster_size=0, duplicate_of=None)
            continue
        projection = project_email(record, email_id)
        email.update(
            record_id=record.record_id,
            cluster_size=len(record.evidence),
            duplicate_of=next(
                (item.duplicate_of for item in record.evidence if item.email_id == email_id),
                None,
            ),
        )
        if projection is not None:
            email["structured"] = projection.model_dump(mode="json")

    rank = {"violation_detected": 0, "financial_alert": 1, "noise": 2}
    safe_emails.sort(key=lambda email: rank.get(email["status"], 3))  # stable: newest-first within a group
    return {
        "status": "success",
        "sweep_timestamp": datetime.now().isoformat(),
        "emails_scanned": len(raw_messages),
        "noise_filtered": sum(email["status"] == "noise" for email in safe_emails),
        "financial_alerts_found": sum(email["status"] != "noise" for email in safe_emails),
        "violations_detected": len(candidates),
        "emails": safe_emails,
        "candidates": candidates,
        "cases": case_payloads,
        "claim_packs": claim_packs,
        "flagged_records": record_payloads,
        "ledger": {
            "schema_version": "haq.ledger.v1",
            "records": record_payloads,
            "summary": summarize_records(record_payloads),
            "ai_status": ledger_status,
        },
        "llm_status": llm_status,
        "ledger_ai_status": ledger_status,
        "ai_assisted_count": sum(
            email.get("llm_assistance", {}).get("status") == "ok" for email in safe_emails
        ),
    }


def search_gmail(
    access_token: str | None = None,
    query: str = "",
    max_results: int = 50,
    demo: bool = False,
    llm_client: LLMClient | None = None,
    llm_settings: LLMSettings | None = None,
    progress: ProgressFn | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    """Perform a live Gmail sweep, or use the synthetic corpus only when demo is explicit."""
    raw_messages: list[dict[str, Any]] = []

    if access_token and access_token.strip():
        raw_messages = fetch_live_gmail(
            access_token.strip(), query, max_results, progress=progress, should_cancel=should_cancel
        )
    elif demo:
        raw_messages = get_demo_email_corpus()
    else:
        raise GmailAccessError("A connected Gmail session is required")

    if progress:
        progress(stage="classifying with Groq" if llm_client else "classifying")
    return filter_and_extract_transactions(raw_messages, llm_client=llm_client, llm_settings=llm_settings)
