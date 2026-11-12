"""Deterministic, explainable detection of failed UPI payments and cancelled orders.

Why this module exists
----------------------
The first sweep treated any email containing "failed" plus *something that looked like
money or a reference* as a payment exception. A GitHub "Run failed: CI" mail matched
because (a) a 12-digit Actions run id looked like a UPI reference and (b) the word
"Refactored" contains "ref". This module replaces those loose substring checks with:

1. Sender trust tiers decided from the parsed email *domain*, never a substring.
2. Word-boundary regexes, so "ref" cannot match inside "refactor" or "refs/heads".
3. A co-occurrence rule: money evidence AND payment context AND a failure/cancel signal.
4. A reasons list on every decision, so the UI can show *why* something was flagged.

Everything here is pure (no network, no storage) and unit-tested.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from email.utils import parseaddr

# --------------------------------------------------------------------------- senders

BLOCKED_SENDER_DOMAINS: tuple[str, ...] = (
    # developer tooling: "failed" here means a build, not a payment
    "github.com", "githubusercontent.com", "gitlab.com", "bitbucket.org", "vercel.com",
    "netlify.com", "render.com", "railway.app", "heroku.com", "sentry.io", "docker.com",
    "npmjs.com", "pypi.org", "atlassian.net", "groq.com",
    # social / newsletters
    "linkedin.com", "facebookmail.com", "twitter.com", "x.com", "medium.com",
    "substack.com", "quora.com", "slack.com", "discord.com", "notion.so",
)

BANK_DOMAINS: tuple[str, ...] = (
    "hdfcbank.net", "hdfcbank.com", "icicibank.com", "sbi.co.in", "onlinesbi.com",
    "sbicard.com", "axisbank.com", "kotak.com", "pnb.co.in", "pnbindia.in",
    "bankofbaroda.com", "bankofbaroda.co.in", "canarabank.com", "unionbankofindia.co.in",
    "indusind.com", "idfcfirstbank.com", "yesbank.in", "federalbank.co.in", "rblbank.com",
    "aubank.in", "paytmbank.com",
)

UPI_APP_DOMAINS: tuple[str, ...] = (
    "phonepe.com", "paytm.com", "cred.club", "npci.org.in", "bhimupi.org.in",
    "mobikwik.com", "freecharge.in", "amazonpay.in", "pay.google.com",
)

MERCHANT_DOMAINS: tuple[str, ...] = (
    # commerce and food
    "amazon.in", "amazon.com", "flipkart.com", "myntra.com", "swiggy.in", "swiggy.com",
    "zomato.com", "blinkit.com", "zeptonow.com", "bigbasket.com", "nykaa.com", "ajio.com",
    "meesho.com", "makemytrip.com", "goibibo.com", "irctc.co.in", "redbus.in",
    "bookmyshow.com", "uber.com", "olacabs.com", "razorpay.com",
    # gaming, in-app purchases and digital storefronts (consumer segment)
    "steampowered.com", "steamcommunity.com", "epicgames.com", "playstation.com", "xbox.com",
    "nintendo.com", "riotgames.com", "supercell.com", "garena.com", "ea.com", "ubisoft.com",
    "roblox.com", "minecraft.net", "googleplay.com", "play.google.com", "g2a.com",
    "dream11.com", "mpl.live", "games24x7.com", "zupee.com", "rummycircle.com",
)


def sender_domain(sender: str) -> str:
    """Return the lower-cased domain of a From header, or '' if there is none."""
    _, address = parseaddr(sender or "")
    if "@" not in address:
        domain = (sender or "").strip().strip("<>").lower()
        return domain if re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", domain) else ""
    return address.rsplit("@", 1)[1].strip().lower()


def _domain_in(domain: str, candidates: tuple[str, ...]) -> bool:
    return any(domain == item or domain.endswith("." + item) for item in candidates)


def classify_sender(sender: str) -> str:
    """Return one of: blocked, bank, upi_app, merchant, unknown."""
    domain = sender_domain(sender)
    if not domain:
        return "unknown"
    if _domain_in(domain, BLOCKED_SENDER_DOMAINS):
        return "blocked"
    if _domain_in(domain, BANK_DOMAINS):
        return "bank"
    if _domain_in(domain, UPI_APP_DOMAINS):
        return "upi_app"
    if _domain_in(domain, MERCHANT_DOMAINS):
        return "merchant"
    return "unknown"


# --------------------------------------------------------------------------- patterns

# `(?<![A-Za-z])` stops "errors 12" or "users 5" being read as "Rs 12" / "Rs 5".
AMOUNT_RE = re.compile(r"(?<![A-Za-z])(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d{1,2})?)", re.IGNORECASE)

OTP_RE = re.compile(
    r"\b(?:otp|one[-\s]time[-\s]password|verification code|security code)\b", re.IGNORECASE
)
PROMO_RE = re.compile(
    r"\b(?:flat \d+% off|sale|deal|discount|coupon|cashback offer|subscribe|newsletter|unlocked)\b",
    re.IGNORECASE,
)

UPI_CTX_RE = re.compile(
    r"\bupi\b|\bvpa\b|@(?:ybl|ibl|axl|okaxis|okhdfcbank|okicici|oksbi|paytm|apl|upi)\b",
    re.IGNORECASE,
)

# A labelled UPI reference ("UPI Ref 4312...", "RRN: ...", "UTR ...").
UPI_REF_RE = re.compile(
    r"\b(?:upi\s+ref(?:erence)?(?:\s+(?:no|id|number))?|upi\s+(?:txn|transaction)\s*(?:id|no|number)?"
    r"|rrn|utr(?:\s*(?:no|number))?)\b\.?[\s:#.\-]*(\d{9,18})\b",
    re.IGNORECASE,
)
# A bare 12-digit number is only a UPI reference when the message is *about UPI*.
BARE_12_DIGIT_RE = re.compile(r"(?<!\d)(\d{12})(?!\d)")
# Generic ids. Word boundaries on the keyword, and the id must contain a digit.
GENERIC_REF_RE = re.compile(
    r"\b(?:txn|transaction|order|ref(?:erence)?|invoice)\b\s*(?:id|no\.?|number|#)?\s*[:#\-]?\s*"
    r"([A-Za-z0-9][A-Za-z0-9_\-]{5,23})\b",
    re.IGNORECASE,
)

PAY_CTX_RE = re.compile(
    r"\b(?:payment|transaction|txn|upi|debited|transfer(?:red)?|paid|purchase|checkout)\b",
    re.IGNORECASE,
)
FAIL_RE = re.compile(
    r"\b(?:fail(?:ed|ure)?|declined|unsuccessful|not\s+(?:successful|completed|processed)"
    r"|could\s+not\s+be\s+(?:completed|processed)|timed?[\s-]*out)\b",
    re.IGNORECASE,
)
DEBIT_RE = re.compile(r"\b(?:debited|deducted|charged|withdrawn)\b", re.IGNORECASE)
REVERSAL_DONE_RE = re.compile(
    r"\breversal\s+credit(?:ed)?\b|\bupi\s+reversal\b|\bcredited\s+back\b"
    r"|\b(?:reversal|refund)\b[^\n]{0,80}\b(?:credited|processed|completed|successful|received)\b"
    r"|\bcredited\b[^\n]{0,80}\b(?:reversal|refund)\b",
    re.IGNORECASE,
)
REFUND_PENDING_RE = re.compile(
    r"\b(?:will\s+be|shall\s+be|is\s+being)\b[^\n]{0,40}\b(?:refund(?:ed)?|reversed|credited)\b"
    r"|\brefund\s+(?:initiated|in\s+progress|pending)\b",
    re.IGNORECASE,
)
ORDER_CANCEL_RE = re.compile(
    r"\b(?:order|booking)\b[^\n]{0,80}\bcancell?ed\b|\bcancell?ed\b[^\n]{0,40}\b(?:order|booking)\b"
    r"|\bcancell?ation\s+of\s+(?:your\s+)?(?:order|booking)\b",
    re.IGNORECASE,
)
ATM_RE = re.compile(r"\batm\b", re.IGNORECASE)
ATM_FAIL_RE = re.compile(
    r"\b(?:not\s+dispensed|cash\s+not\s+dispensed|failed\s+to\s+dispense|dispense\s+incomplete|incomplete)\b",
    re.IGNORECASE,
)
OVERDUE_RE = re.compile(r"\boverdue\b", re.IGNORECASE)
INVOICE_RE = re.compile(r"\binvoice\b", re.IGNORECASE)
# A business resolution signal: the buyer confirms the invoice was paid. This is the
# counterpart of `refund_credited` for suppliers and lets the ledger close an MSME case.
INVOICE_PAID_RE = re.compile(
    r"\b(?:payment|amount|invoice|remittance)\b[^\n]{0,80}\b(?:received|paid|settled|cleared|remitted)\b"
    r"|\bpaid\b[^\n]{0,60}\binvoice\b"
    r"|\bremittance\s+advice\b",
    re.IGNORECASE,
)
# Extra context for the cheap header-only body-opening gate. Business and gaming mail
# often says "purchase order", "in-app purchase" or "battle pass" instead of "UPI".
EXTRA_CONTEXT_RE = re.compile(
    r"\b(?:in[- ]app purchase|battle pass|gaming|game|top[- ]?up|purchase order"
    r"|remittance advice|tax invoice|gstin|vendor|supplier|proforma)\b",
    re.IGNORECASE,
)

# Devanagari combining marks are not \w, so \b is unreliable; match these as substrings.
HINDI_FAIL = ("विफल", "असफल", "फेल")
HINDI_CANCEL = ("रद्द",)

# Kinds that are worth a user's attention (they become "violation_detected").
EXCEPTION_KINDS = frozenset(
    {"upi_failed_debited", "upi_failed", "order_cancelled", "atm_failure", "overdue_invoice"}
)


@dataclass(frozen=True, slots=True)
class Signal:
    kind: str  # an EXCEPTION_KINDS member, debit, refund_credited, or noise
    channel: str  # UPI, ORDER, ATM, MSME, CARD, or ""
    tag: str  # short human label for the UI
    sender_tier: str
    amount_paise: int | None = None
    ref: str | None = None
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_noise(self) -> bool:
        return self.kind == "noise"

    @property
    def is_exception(self) -> bool:
        return self.kind in EXCEPTION_KINDS

    @property
    def is_resolution(self) -> bool:
        return self.kind in {"refund_credited", "invoice_paid"}


def parse_amount(text: str) -> int | None:
    match = AMOUNT_RE.search(text)
    if not match:
        return None
    try:
        paise = round(float(match.group(1).replace(",", "")) * 100)
    except ValueError:
        return None
    return paise if paise > 0 else None


def find_reference(text: str, *, upi_context: bool) -> str | None:
    """Find a transaction reference; a bare 12-digit run is only accepted in UPI context."""
    labelled = UPI_REF_RE.search(text)
    if labelled:
        return labelled.group(1)
    for match in GENERIC_REF_RE.finditer(text):
        candidate = match.group(1)
        if any(ch.isdigit() for ch in candidate):
            return candidate
    if upi_context:
        bare = BARE_12_DIGIT_RE.search(text)
        if bare:
            return bare.group(1)
    return None


def _noise(tier: str, tag: str, *reasons: str) -> Signal:
    return Signal("noise", "", tag, tier, reasons=tuple(reasons))


def classify_message(sender: str, subject: str, snippet: str, body: str) -> Signal:
    """Decide what one email is. Every branch records why."""
    tier = classify_sender(sender)
    if tier == "blocked":
        return _noise(tier, "Developer / social notification filtered", f"blocked sender domain {sender_domain(sender)}")

    text = f"{subject}\n{snippet}\n{body}"
    amount = parse_amount(text)
    upi_ctx = bool(UPI_CTX_RE.search(text)) or tier == "upi_app"
    ref = find_reference(text, upi_context=bool(UPI_CTX_RE.search(text)))

    if OTP_RE.search(text) and amount is None:
        return _noise(tier, "OTP / verification filtered", "OTP wording with no amount")
    fail = bool(FAIL_RE.search(text)) or any(word in text for word in HINDI_FAIL)
    cancel = bool(ORDER_CANCEL_RE.search(text)) or any(word in text for word in HINDI_CANCEL)
    # "Refund will be credited" is a promise, not a completed reversal.
    reversal_done = bool(REVERSAL_DONE_RE.search(text)) and not REFUND_PENDING_RE.search(text)
    if PROMO_RE.search(text) and tier not in {"bank", "upi_app"} and not (fail or cancel or reversal_done):
        return _noise(tier, "Promotional noise filtered", "promotional wording, no payment event")
    if amount is None and ref is None:
        return _noise(tier, "Non-financial notification filtered", "no amount or transaction reference")
    trusted = tier in {"bank", "upi_app", "merchant"}
    pay_ctx = bool(PAY_CTX_RE.search(text))
    if not trusted and not (pay_ctx or cancel):
        return _noise(tier, "Not payment related", "unknown sender and no payment wording")

    reasons: list[str] = []
    if trusted:
        reasons.append(f"sender is a known {tier.replace('_', ' ')} domain ({sender_domain(sender)})")
    if amount is not None:
        reasons.append(f"amount found: ₹{amount / 100:,.2f}")
    if ref:
        reasons.append(f"reference found: {ref}")
    debit = bool(DEBIT_RE.search(text))

    if ATM_RE.search(text) and (ATM_FAIL_RE.search(text) or fail):
        return Signal("atm_failure", "ATM", "ATM withdrawal failed; review evidence", tier, amount, ref,
                      (*reasons, "ATM wording with failure wording"))
    if INVOICE_RE.search(text) and OVERDUE_RE.search(text):
        return Signal("overdue_invoice", "MSME", "Overdue invoice; review evidence", tier, amount, ref,
                      (*reasons, "invoice wording with overdue wording"))
    if INVOICE_RE.search(text) and INVOICE_PAID_RE.search(text):
        return Signal("invoice_paid", "MSME", "Invoice payment confirmation", tier, amount, ref,
                      (*reasons, "invoice wording with payment-received wording"))
    if cancel and not reversal_done and (amount is not None or ref or trusted):
        why = "refund still pending" if REFUND_PENDING_RE.search(text) else "no refund confirmation in this email"
        return Signal("order_cancelled", "ORDER", "Cancelled order; check the refund", tier, amount, ref,
                      (*reasons, "order cancellation wording", why))
    if fail and pay_ctx and (upi_ctx or trusted):
        channel = "UPI" if upi_ctx else "CARD"
        if debit:
            return Signal("upi_failed_debited", channel, "Failed payment with money debited; review evidence",
                          tier, amount, ref, (*reasons, "failure wording", "debit wording: money may have left the account"))
        return Signal("upi_failed", channel, "Failed payment; check whether money was debited", tier, amount, ref,
                      (*reasons, "failure wording"))
    if reversal_done:
        return Signal("refund_credited", "UPI" if upi_ctx else "CARD", "Reversal / refund credit", tier, amount,
                      ref, (*reasons, "reversal or refund credited"))
    if debit and amount is not None:
        return Signal("debit", "UPI" if upi_ctx else "CARD", "Debit alert", tier, amount, ref,
                      (*reasons, "debit wording"))
    return _noise(tier, "Financial wording but no payment event", "no failure, cancellation, debit or refund pattern")


def looks_payment_related(subject: str, snippet: str) -> bool:
    """Cheap header-only gate used before we decide to open a message body."""
    text = f"{subject}\n{snippet}"
    return bool(
        AMOUNT_RE.search(text) or UPI_CTX_RE.search(text) or PAY_CTX_RE.search(text)
        or ORDER_CANCEL_RE.search(text) or REVERSAL_DONE_RE.search(text) or INVOICE_RE.search(text)
        or EXTRA_CONTEXT_RE.search(text)
        or any(word in text for word in (*HINDI_FAIL, *HINDI_CANCEL))
    )
