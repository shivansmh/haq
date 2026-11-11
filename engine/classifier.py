"""Haq Classifier: Unified Intent & Entity Extraction Engine.

Classifies user chat prompts and document inputs into one of the four statutory rights categories:
1. failed_payment (RBI Harmonised TAT framework: R-001 to R-006)
2. msme_dues (MSMED Act 2006, Section 15 & 16: R-007 to R-010)
3. unclaimed_wealth (UDGAM, IEPF, Bima Bharosa, EPFO: R-011 to R-015)
4. general_rights (Consumer forum, general chargebacks)
"""

from __future__ import annotations

import re
from typing import Any, Literal

Category = Literal["failed_payment", "msme_dues", "unclaimed_wealth", "general_rights"]

# Semantic keywords and regex patterns for rapid, deterministic classification
PATTERNS: dict[Category, tuple[re.Pattern, ...]] = {
    "failed_payment": (
        re.compile(r"\b(upi|gpay|phonepe|paytm|bhim|atm|debit(?:ed)?|cash not dispensed)\b", re.IGNORECASE),
        re.compile(r"\b(failed (?:payment|transaction)|transaction failed|delayed reversal|refund pending)\b", re.IGNORECASE),
        re.compile(r"\b(swiggy|zomato|amazon pay|razorpay|tat|turnaround time|rbi penalty|100 per day)\b", re.IGNORECASE),
        re.compile(r"\b(bank debited|money deducted|credited back|reversal delay)\b", re.IGNORECASE),
    ),
    "msme_dues": (
        re.compile(r"\b(invoice|client|buyer|supplier|vendor|freelancer|contractor)\b", re.IGNORECASE),
        re.compile(r"\b(unpaid (?:invoice|bill)|payment overdue|overdue by|delayed payment)\b", re.IGNORECASE),
        re.compile(r"\b(msme|msmed|samadhaan|section 15|section 16|43b\(h\)|37\(2\)\(g\))\b", re.IGNORECASE),
        re.compile(r"\b(45 days|15 days|compound interest|bank rate|msefc)\b", re.IGNORECASE),
    ),
    "unclaimed_wealth": (
        re.compile(r"\b(unclaimed|dormant|inoperative|forgotten money|old account)\b", re.IGNORECASE),
        re.compile(r"\b(grandfather|father|relative|deceased|heir|nominee)\b", re.IGNORECASE),
        re.compile(r"\b(udgam|dea fund|iepf|shares|dividend|bima bharosa|insurance policy)\b", re.IGNORECASE),
        re.compile(r"\b(epfo|provident fund|pf balance|uan|member id|inoperative pf)\b", re.IGNORECASE),
    ),
}

MONEY_PATTERN = re.compile(
    r"(?:₹|rs\.?|inr)?\s*(\d[\d,]*(?:\.\d{1,2})?)\s*(?:(lakhs?|crores?|k)\b)?", re.IGNORECASE
)
DAYS_PATTERN = re.compile(r"(\d+)\s*(?:days?|months?|weeks?)\s*(?:ago|overdue|late|pending)?", re.IGNORECASE)
REF_PATTERN = re.compile(r"\b(?:rrn|utr|ref|txn|invoice|inv)[\s:#-]*([A-Za-z0-9_-]{6,18})\b", re.IGNORECASE)


def extract_entities(text: str) -> dict[str, Any]:
    """Extract financial entities (amounts, dates/days, references, entities) from text."""
    entities: dict[str, Any] = {
        "amount_paise": None,
        "amount_inr": None,
        "days": None,
        "ref": None,
        "counterparty": None,
    }

    # Extract monetary amount
    for match in MONEY_PATTERN.finditer(text):
        raw_num = match.group(1).replace(",", "")
        scale = (match.group(2) or "").lower()
        try:
            val = float(raw_num)
            if "lakh" in scale:
                val *= 100_000
            elif "crore" in scale:
                val *= 10_000_000
            elif scale == "k":
                val *= 1_000

            if val > 0 and (entities["amount_inr"] is None or val > entities["amount_inr"]):
                entities["amount_inr"] = round(val)
                entities["amount_paise"] = round(val * 100)
        except ValueError:
            continue

    # Extract days or timeframe
    day_match = DAYS_PATTERN.search(text)
    if day_match:
        try:
            entities["days"] = int(day_match.group(1))
        except ValueError:
            pass

    # Extract reference or transaction ID
    ref_match = REF_PATTERN.search(text)
    if ref_match:
        entities["ref"] = ref_match.group(1)

    # Detect notable counterparties / apps
    notable = ["swiggy", "zomato", "hdfc", "sbi", "icici", "axis", "kotak", "phonepe", "gpay", "paytm", "cred"]
    for entity in notable:
        if re.search(rf"\b{entity}\b", text, re.IGNORECASE):
            entities["counterparty"] = entity.upper()
            break

    return entities


def classify_prompt(prompt: str, filename: str | None = None) -> dict[str, Any]:
    """Classify user query or document and return routing metadata."""
    combined_text = f"{prompt} {filename or ''}".lower()
    scores: dict[Category, int] = {"failed_payment": 0, "msme_dues": 0, "unclaimed_wealth": 0, "general_rights": 0}

    for cat, pattern_list in PATTERNS.items():
        for pat in pattern_list:
            matches = pat.findall(combined_text)
            scores[cat] += len(matches)

    # If document attached, check file extension hints
    if filename:
        fn = filename.lower()
        if any(w in fn for w in ("invoice", "bill", "tax")):
            scores["msme_dues"] += 3
        elif any(w in fn for w in ("statement", "bank", "upi", "passbook")):
            scores["failed_payment"] += 3
        elif any(w in fn for w in ("share", "dividend", "iepf", "pf", "epfo")):
            scores["unclaimed_wealth"] += 3

    # Pick highest scoring category
    best_cat: Category = max(scores, key=scores.get) # type: ignore
    max_score = scores[best_cat]

    if max_score == 0:
        # Default fallback if query is ambiguous
        best_cat = "failed_payment"
        confidence = 0.50
    else:
        confidence = min(0.98, 0.65 + (max_score * 0.10))

    entities = extract_entities(prompt)

    # Build category specific titles, summaries, and primary statutory laws
    if best_cat == "failed_payment":
        title = "Failed Payment & Statutory Reversal Compensation"
        statutory_law = "Reserve Bank of India (RBI) Harmonised TAT Circular DPSS.CO.PD No.629/02.01.014/2019-20"
        summary = (
            "This text appears related to a failed payment or delayed reversal. "
            "The RBI turnaround-time material may be relevant, but the transaction facts and current rule status "
            "must be checked before treating compensation as due."
        )
        suggested_route = "payment_flow"
    elif best_cat == "msme_dues":
        title = "MSME Delayed Invoice & Statutory Compounding Interest"
        statutory_law = "MSMED Act 2006 (Sections 15 & 16) & Income-tax Act Section 43B(h)/37(2)(g)"
        summary = (
            "This text appears related to an unpaid MSME invoice. Sections 15 and 16 of the MSMED Act may be relevant, "
            "but the supplier status, agreement, dates, and current bank-rate inputs must be verified before calculating a claim."
        )
        suggested_route = "msme_flow"
    elif best_cat == "unclaimed_wealth":
        title = "Unclaimed Assets & Dormant Wealth Recovery"
        statutory_law = "UDGAM Portal (RBI DEA Fund), MCA IEPF Authority Rules, & EPFO Inoperative Regulations"
        summary = (
            "This text appears related to an unclaimed-asset search. The official UDGAM, IEPF, Bima Bharosa, or EPFO "
            "route may be relevant; eligibility and claimability must be confirmed with the relevant portal."
        )
        suggested_route = "unclaimed_flow"
    else:
        title = "General Consumer & Financial Rights"
        statutory_law = "Consumer Protection Act, 2019 & Banking Ombudsman Guidelines"
        summary = "This is a general rights route. Haq can suggest sources, but it cannot determine a legal conclusion from this text alone."
        suggested_route = "general_flow"

    return {
        "category": best_cat,
        "confidence": confidence,
        "title": title,
        "summary": summary,
        "statutory_law": statutory_law,
        "suggested_route": suggested_route,
        "extracted_entities": entities,
        "prompt": prompt,
    }
