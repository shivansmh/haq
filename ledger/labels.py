"""Small, deterministic label helpers for the flagged-record ledger.

These are deliberately boring: a brand/vertical lookup makes the JSON useful to a
human and to the UI, but it never changes the legal assessment or the amount.
The optional model can only *suggest* labels; deterministic values win.
"""

from __future__ import annotations

import re

from api.upi_signals import sender_domain

from .models import Segment, Vertical

# (canonical merchant, vertical, aliases). Order matters: the first match wins.
_BRANDS: tuple[tuple[str, Vertical, tuple[str, ...]], ...] = (
    # gaming and in-app purchases
    ("Steam", "gaming", ("steam", "steampowered")),
    ("Epic Games", "gaming", ("epic games", "epicgames", "fortnite")),
    ("Google Play", "gaming", ("google play", "googleplay", "play store")),
    ("Riot Games", "gaming", ("riot games", "riotgames", "valorant", "league of legends")),
    ("PlayStation", "gaming", ("playstation", "psn")),
    ("Xbox", "gaming", ("xbox", "microsoft store")),
    ("Nintendo", "gaming", ("nintendo", "eshop")),
    ("Supercell", "gaming", ("supercell", "clash of clans", "clash royale", "brawl stars")),
    ("Garena", "gaming", ("garena", "free fire")),
    ("BGMI", "gaming", ("bgmi", "pubg", "battlegrounds mobile")),
    ("Roblox", "gaming", ("roblox", "robux")),
    ("Minecraft", "gaming", ("minecraft", "minecoins")),
    ("Dream11", "gaming", ("dream11", "dream 11")),
    ("MPL", "gaming", ("mpl", "mobile premier league")),
    ("RummyCircle", "gaming", ("rummycircle", "rummy circle", "rummy")),
    ("Zupee", "gaming", ("zupee",)),
    ("G2A", "gaming", ("g2a",)),
    # food delivery
    ("Swiggy", "food_delivery", ("swiggy",)),
    ("Zomato", "food_delivery", ("zomato",)),
    ("Blinkit", "food_delivery", ("blinkit",)),
    ("Zepto", "food_delivery", ("zepto",)),
    ("BigBasket", "food_delivery", ("bigbasket", "big basket")),
    ("Domino's", "food_delivery", ("dominos", "domino's")),
    ("KFC", "food_delivery", ("kfc",)),
    ("McDonald's", "food_delivery", ("mcdonald", "mcdonalds", "mcdonald's")),
    # commerce
    ("Amazon", "ecommerce", ("amazon",)),
    ("Flipkart", "ecommerce", ("flipkart",)),
    ("Myntra", "ecommerce", ("myntra",)),
    ("Ajio", "ecommerce", ("ajio",)),
    ("Meesho", "ecommerce", ("meesho",)),
    ("Nykaa", "ecommerce", ("nykaa",)),
    ("eBay", "ecommerce", ("ebay",)),
    # travel
    ("MakeMyTrip", "travel", ("makemytrip", "make my trip")),
    ("Goibibo", "travel", ("goibibo",)),
    ("IRCTC", "travel", ("irctc",)),
    ("RedBus", "travel", ("redbus", "red bus")),
    ("Uber", "travel", ("uber",)),
    ("Ola", "travel", ("olacabs", "ola cabs", "ola")),
    ("IndiGo", "travel", ("indigo", "indigo airlines")),
    ("Air India", "travel", ("air india",)),
    # utilities
    ("Jio", "utilities", ("jio", "reliance jio")),
    ("Airtel", "utilities", ("airtel",)),
    ("Vi", "utilities", ("vodafone idea", "vi recharge")),
    ("BSNL", "utilities", ("bsnl",)),
    # finance (fallback only; the merchant is usually the counterparty)
    ("HDFC Bank", "finance", ("hdfc bank", "hdfcbank")),
    ("ICICI Bank", "finance", ("icici bank", "icicibank")),
    ("State Bank of India", "finance", ("state bank of india", "sbi")),
    ("Axis Bank", "finance", ("axis bank",)),
    ("Kotak Mahindra Bank", "finance", ("kotak",)),
    ("Punjab National Bank", "finance", ("punjab national bank", "pnb")),
    ("PhonePe", "finance", ("phonepe",)),
    ("Paytm", "finance", ("paytm",)),
    ("Razorpay", "finance", ("razorpay",)),
)

_BRAND_PATTERNS = tuple(
    (
        canonical,
        vertical,
        re.compile(r"\b(?:" + "|".join(re.escape(alias) for alias in aliases) + r")\b", re.I),
    )
    for canonical, vertical, aliases in _BRANDS
)

_BUSINESS_RE = re.compile(
    r"\b(?:tax invoice|gstin|gst\s*(?:no|number)|purchase order|p\.?o\.?\s*(?:no|number)"
    r"|vendor|supplier|accounts payable|remittance advice|proforma|udyam|msme"
    r"|b2b|business account|current account|enterprise)\b",
    re.I,
)
_GAMING_RE = re.compile(
    r"\b(?:in[- ]app purchase|battle pass|game|gaming|skin|v[- ]?bucks|robux|top[- ]?up"
    r"|loot box|season pass|esports)\b",
    re.I,
)
_FOOD_RE = re.compile(r"\b(?:food|restaurant|biryani|pizza|grocery|quick commerce)\b", re.I)
_TRAVEL_RE = re.compile(r"\b(?:flight|hotel|train|bus|booking|ticket|cab ride)\b", re.I)
_UTILITY_RE = re.compile(r"\b(?:electricity|broadband|water bill|gas bill|recharge|postpaid|prepaid)\b", re.I)
_FREEMAIL = {"gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "yahoo.in", "icloud.com", "proton.me"}
_GENERIC_LOCAL = {
    "accounts", "billing", "support", "no-reply", "noreply", "alerts", "notifications",
    "orders", "payments", "payment", "mail", "info", "hello", "team", "service",
}
_AT_TO_RE = re.compile(
    r"\b(?:at|to|towards|merchant[:\s]+)\s+"
    r"([A-Z][A-Za-z0-9&'.\-]*(?:\s+[A-Z][A-Za-z0-9&'.\-]*){0,2})"
)
_STOPWORDS = {
    "Your", "The", "This", "That", "UPI", "Rs", "INR", "Account", "Bank", "Payment",
    "Transaction", "Order", "Invoice", "Dear", "Cash", "Card", "Amount", "Ref", "ATM",
}


def _domain_merchant(sender: str) -> str | None:
    domain = sender_domain(sender)
    if not domain or domain in _FREEMAIL:
        return None
    first = domain.split(".")[0]
    if first in _GENERIC_LOCAL or len(first) < 3:
        return None
    words = [word for word in re.split(r"[-_]", first) if word]
    if not words:
        return None
    return " ".join(word.capitalize() for word in words)


def detect_merchant(sender: str, *texts: str) -> str | None:
    """Return a canonical merchant, else a domain-style business name, else a phrase."""
    haystack = " ".join([*(str(text or "") for text in texts), str(sender or "")])
    # Prefer a real counterparty over the bank that sent the alert.
    for canonical, vertical, pattern in sorted(_BRAND_PATTERNS, key=lambda item: item[1] == "finance"):
        if pattern.search(haystack):
            return canonical
    match = _AT_TO_RE.search(haystack)
    if match:
        candidate = " ".join(match.group(1).split()).rstrip(".,;:")
        if candidate.split()[0] not in _STOPWORDS and len(candidate) >= 3:
            return candidate
    return _domain_merchant(sender)


def detect_vertical(claim_type: str, merchant: str | None, *texts: str) -> Vertical:
    if claim_type == "msme_invoice_overdue":
        return "business"
    haystack = " ".join(str(text or "") for text in texts)
    if merchant:
        for canonical, vertical, _pattern in _BRAND_PATTERNS:
            if canonical == merchant:
                return vertical
    if _BUSINESS_RE.search(haystack):
        return "business"
    if _GAMING_RE.search(haystack):
        return "gaming"
    if _FOOD_RE.search(haystack):
        return "food_delivery"
    if _TRAVEL_RE.search(haystack):
        return "travel"
    if _UTILITY_RE.search(haystack):
        return "utilities"
    return "other"


def detect_segment(claim_type: str, vertical: Vertical, *texts: str) -> Segment:
    if claim_type == "msme_invoice_overdue" or vertical == "business":
        return "business"
    if _BUSINESS_RE.search(" ".join(str(text or "") for text in texts)):
        return "business"
    return "consumer"


def labels_for(
    *,
    claim_type: str,
    channel: str,
    merchant: str | None,
    vertical: Vertical,
    segment: Segment,
    resolution_received: bool,
    rule_status: str,
    signal_kinds: set[str],
) -> list[str]:
    labels: list[str] = [claim_type]
    if channel:
        labels.append(channel.lower())
    if merchant:
        labels.append("merchant:" + merchant.casefold().replace(" ", "-"))
    labels.extend([vertical, segment])
    if vertical == "gaming":
        labels.append("gaming")
    if segment == "business":
        labels.append("business")
    labels.append("refund-received" if resolution_received else "refund-pending")
    if rule_status != "None":
        labels.append("rule-" + rule_status.casefold())
    for kind in sorted(signal_kinds):
        if kind not in labels and kind not in {"debit"}:
            labels.append(kind)
    return list(dict.fromkeys(labels))


def recommended_actions(
    *,
    claim_type: str,
    status: str,
    resolution_received: bool,
    compliance: str,
    segment: Segment,
    has_origin: bool = True,
) -> list[str]:
    """Plain next steps. Never a promise of compensation."""
    if resolution_received and not has_origin:
        if claim_type == "msme_invoice_overdue":
            noun, original = "payment", "invoice or remittance"
        elif claim_type == "atm_cash_not_dispensed":
            noun, original = "cash reversal", "ATM withdrawal"
        else:
            noun, original = "refund", "transaction"
        return [
            f"A {noun} confirmation was found, but the original {original} was not. "
            f"Check it against your records before treating it as resolved. "
            f"No legal timing or compensation is assessed until the {original} is matched."
        ]

    if claim_type == "msme_invoice_overdue":
        actions = [
            "Send a written demand to the buyer's accounts team quoting the invoice number and due date.",
            "Keep the invoice, delivery or acceptance proof, and the buyer's acknowledgement together.",
            "If unpaid, ask about the MSME Facilitation Council route (Section 18) and record every reminder.",
        ]
        if resolution_received:
            actions.insert(0, "Payment appears received; confirm the credited amount matches the invoice.")
        return actions

    if resolution_received:
        if compliance == "on_time":
            return ["Refund appears received on time. Keep this record with the reference for your files."]
        if compliance != "late":
            return [
                "Refund appears received. Haq could not assess legal timing, so no compensation is "
                "calculated. Keep the credit confirmation with the transaction evidence."
            ]
        return [
            "The refund appears late under the verified rule. Ask the bank or payment app to confirm any applicable compensation in writing.",
        ]

    if claim_type == "atm_cash_not_dispensed":
        actions = [
            "Raise a complaint with the ATM-issuing bank and keep the ATM ID and transaction reference.",
            "Ask for the ATM journal/trace and a written reversal timeline.",
            "If unresolved, escalate to the bank's Principal Nodal Officer and then the RBI Ombudsman.",
        ]
    elif claim_type == "order_cancelled_refund_delayed":
        actions = [
            "Ask the merchant for the refund reference and expected credit date in writing.",
            "If the merchant stalls, raise it with the payment provider or card issuer.",
            "Keep the cancellation email, original debit and your bank statement together.",
        ]
    elif claim_type == "card_debited_order_unconfirmed":
        actions = [
            "Ask the merchant whether the order was confirmed and request a cancellation reference.",
            "If there is no order, dispute the charge with the card issuer and keep the merchant reply.",
            "Track the credit against the rule's turnaround time before escalating.",
        ]
    else:
        actions = [
            "Raise a written complaint with the payment app and your bank quoting the transaction reference.",
            "Ask for the reversal reference and the date the credit was processed.",
            "If the refund is still missing, escalate to the bank's Principal Nodal Officer and the RBI Ombudsman.",
        ]
    if segment == "business":
        actions.append("Save the same evidence in your business accounts so it can be reconciled later.")
    return actions
