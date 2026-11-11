"""Synthetic bank-statement generator for Haq (T2 test set).

Every file this script writes is FAKE test data. The layouts are invented and do
not copy any real bank's format. Run from the repository root:
    python generate_synthetic.py
"""

import csv
import random
import re
from datetime import date, timedelta
from pathlib import Path

import pdfplumber
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path("data/synthetic")
MERCHANTS = ["SAMPLEMART", "DEMOCAFE", "TESTFUEL", "MOCKPHARMA", "FAKEBOOKS", "DUMMYCAB"]
LAYOUTS = {
    "alpha": {
        "date_fmt": "%d/%m/%Y",
        "style": "split",
        "grid": True,
        "headers": ["Date", "Narration", "Debit", "Credit", "Balance"],
        "widths": [60, 200, 65, 65, 75],
    },
    "beta": {
        "date_fmt": "%d-%b-%y",
        "style": "split",
        "grid": True,
        "headers": ["Txn Date", "Particulars", "Withdrawal", "Deposit", "Balance"],
        "widths": [60, 200, 65, 65, 75],
    },
    "gamma": {
        "date_fmt": "%d %b %Y",
        "style": "signed",
        "grid": False,
        "headers": ["Date", "Details", "Amount", "Balance"],
        "widths": [75, 150, 95, 95],
    },
    "delta": {
        "date_fmt": "%Y-%m-%d",
        "style": "brackets",
        "grid": False,
        "headers": ["Date", "Description", "Amount (INR)", "Balance (INR)"],
        "widths": [65, 160, 95, 95],
    },
}
SCAN_PATTERNS = {
    "pan": r"\b[A-Z]{5}\d{4}[A-Z]\b",
    "aadhaar_grouped": r"\b\d{4} \d{4} \d{4}\b",
    "email": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "phone": r"\b[6-9]\d{9}\b",
    "long_digits": r"\b\d{9,18}\b",
}


def fmt_money(paise):
    """Format integer paise as rupees with Indian digit grouping, e.g. 1,25,000.00."""
    rupees, rest = divmod(paise, 100)
    digits = str(rupees)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        digits = ",".join(parts + [tail])
    return f"{digits}.{rest:02d}"


def make_ref(rng):
    return str(rng.randrange(10**11, 10**12))  # always 12 digits, like a UPI reference


def make_txn(
    day,
    narration,
    debit=0,
    credit=0,
    channel="OTHER",
    ref="",
    scenario="normal",
    truth="",
    reversal_date=None,
    failure="no",
):
    return {
        "date": day,
        "narration": narration,
        "debit": debit,
        "credit": credit,
        "channel": channel,
        "ref": ref,
        "scenario": scenario,
        "truth": truth,
        "reversal_date": reversal_date,
        "failure": failure,
    }


def failure_case(rng, start, scenario, channel, delay, with_ref):
    """A payment that failed. delay=0 means it is never reversed."""
    day = start + timedelta(days=rng.randrange(1, 22))
    amount = rng.randrange(200, 4000) * 100
    merchant = rng.choice(MERCHANTS)
    ref = make_ref(rng) if channel == "UPI" else ""
    narration = (
        f"UPI/{ref}/{merchant}/sample@fakebank" if channel == "UPI" else "ATM WDL SAMPLE ATM 02"
    )
    reversal_day = day + timedelta(days=delay) if delay else None
    rows = [
        make_txn(
            day,
            narration,
            debit=amount,
            channel=channel,
            ref=ref,
            scenario=scenario,
            truth="reversed" if delay else "unreversed",
            reversal_date=reversal_day,
            failure="yes",
        )
    ]
    if delay:
        if channel == "UPI":
            back = f"UPI REV/{ref}/{merchant}" if with_ref else "REVERSAL OF FAILED TXN"
        else:
            back = "ATM CASH REV SAMPLE ATM 02"
        rows.append(
            make_txn(
                reversal_day,
                back,
                credit=amount,
                channel=channel,
                ref=ref if with_ref else "",
                scenario="reversal_credit",
            )
        )
    return rows


def build_events(rng, start):
    events = [
        make_txn(
            start + timedelta(days=1),
            "SALARY SAMPLECORP",
            credit=rng.randrange(40000, 70000) * 100,
            channel="NEFT",
        )
    ]
    for _ in range(26):  # ordinary traffic that must NOT look like a failure
        day = start + timedelta(days=rng.randrange(0, 29))
        kind = rng.choice(["upi", "upi", "upi", "pos", "atm", "nach"])
        amount = rng.randrange(50, 3000) * 100
        if kind == "upi":
            ref = make_ref(rng)
            narration = f"UPI/{ref}/{rng.choice(MERCHANTS)}/sample@fakebank"
            events.append(
                make_txn(day, narration, debit=amount, channel="UPI", ref=ref, truth="unreversed")
            )
        elif kind == "pos":
            events.append(
                make_txn(
                    day,
                    f"POS {rng.choice(MERCHANTS)} SAMPLECITY",
                    debit=amount,
                    channel="POS",
                    truth="unreversed",
                )
            )
        elif kind == "atm":
            events.append(
                make_txn(
                    day, "ATM WDL SAMPLE ATM 01", debit=amount, channel="ATM", truth="unreversed"
                )
            )
        else:
            events.append(
                make_txn(
                    day, "NACH DR SAMPLE LOAN EMI", debit=amount, channel="NACH", truth="unreversed"
                )
            )
    events += failure_case(rng, start, "upi_reversed_ontime", "UPI", 1, True)
    events += failure_case(rng, start, "upi_reversed_late_noref", "UPI", 6, False)
    events += failure_case(rng, start, "upi_never_reversed", "UPI", 0, False)
    events += failure_case(rng, start, "atm_reversed", "ATM", 5, True)
    events += failure_case(rng, start, "atm_never_reversed", "ATM", 0, False)
    day = start + timedelta(days=rng.randrange(1, 22))  # lookalike: same-amount credit, unrelated
    amount = rng.randrange(200, 4000) * 100
    ref = make_ref(rng)
    events.append(
        make_txn(
            day,
            f"UPI/{ref}/{rng.choice(MERCHANTS)}/sample@fakebank",
            debit=amount,
            channel="UPI",
            ref=ref,
            scenario="lookalike_credit",
            truth="unreversed",
        )
    )
    events.append(
        make_txn(
            day + timedelta(days=3), "SALARY ARREARS SAMPLECORP", credit=amount, channel="NEFT"
        )
    )
    return events


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.drawString(40, 20, "SYNTHETIC TEST DATA - generated by Haq - not a real statement")
    canvas.restoreState()


def render_pdf(path, name, layout, rows, start, end, opening, closing):
    styles = getSampleStyleSheet()
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, leading=10)
    fmt = layout["date_fmt"]
    story = [
        Paragraph("SYNTHETIC TEST DATA - NOT A REAL STATEMENT", styles["Heading2"]),
        Paragraph(f"Synthetic Bank {name.title()} - Statement of Account", styles["Heading3"]),
        Paragraph(
            f"Account holder: SAMPLE HOLDER. Account: SAMPLE-ACCOUNT. "
            f"Period: {start.strftime(fmt)} to {end.strftime(fmt)}",
            styles["Normal"],
        ),
        Spacer(1, 12),
    ]
    ncols = len(layout["headers"])
    data = [
        layout["headers"],
        [start.strftime(fmt), Paragraph("OPENING BALANCE", small)]
        + [""] * (ncols - 3)
        + [fmt_money(opening)],
    ]
    for t in rows:
        date_text, narration, balance = (
            t["date"].strftime(fmt),
            Paragraph(t["narration"], small),
            fmt_money(t["balance"]),
        )
        if layout["style"] == "split":
            data.append(
                [
                    date_text,
                    narration,
                    fmt_money(t["debit"]) if t["debit"] else "",
                    fmt_money(t["credit"]) if t["credit"] else "",
                    balance,
                ]
            )
        elif layout["style"] == "signed":
            amount = f"{fmt_money(t['debit'])} Dr" if t["debit"] else f"{fmt_money(t['credit'])} Cr"
            data.append([date_text, narration, amount, balance + " Cr"])
        else:
            amount = f"({fmt_money(t['debit'])})" if t["debit"] else fmt_money(t["credit"])
            data.append([date_text, narration, amount, balance])
    table = Table(data, colWidths=layout["widths"], repeatRows=1)
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
    ]
    if layout["grid"]:
        style.append(("GRID", (0, 0), (-1, -1), 0.25, colors.grey))
    table.setStyle(TableStyle(style))
    story += [
        table,
        Spacer(1, 12),
        Paragraph(f"Closing balance: {fmt_money(closing)}", styles["Normal"]),
    ]
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,
        bottomMargin=40,
        title="SYNTHETIC statement",
        author="haq-synthetic-generator",
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def scan_pdf(path):
    """Return the names of identity-like patterns found in the PDF text (empty list = clean)."""
    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    text = re.sub(
        r"/\d{12}/", "/REF/", text
    )  # 12-digit UPI references sit between slashes; expected
    return [label for label, pattern in SCAN_PATTERNS.items() if re.search(pattern, text)]


def main():
    rng = random.Random(20261111)
    labels, manifest = [], []
    for name, layout in LAYOUTS.items():
        (OUT / name).mkdir(parents=True, exist_ok=True)
        for k in range(1, 6):
            start = date(2026, k, 1)
            end = start + timedelta(days=29)
            rows = sorted(build_events(rng, start), key=lambda t: t["date"])
            opening = rng.randrange(80000, 150000) * 100
            balance = opening
            for number, t in enumerate(rows, start=1):
                balance += t["credit"] - t["debit"]
                assert balance >= 0, "balance went negative; adjust amounts"
                t["balance"], t["row_number"] = balance, number
            sid = f"SYN-{name}-{k:02d}"
            path = OUT / name / f"{name}_{k:02d}.pdf"
            render_pdf(path, name, layout, rows, start, end, opening, balance)
            hits = scan_pdf(path)
            manifest.append(
                [
                    sid,
                    "SYNTHETIC",
                    f"synthetic_{name}",
                    f"{start}..{end}",
                    "synthetic",
                    "n/a",
                    "generator-scan",
                    "yes" if not hits else "NO:" + "+".join(hits),
                    "n/a",
                ]
            )
            for t in rows:
                if t["debit"]:
                    labels.append(
                        [
                            sid,
                            t["row_number"],
                            t["date"],
                            t["debit"],
                            t["channel"],
                            t["ref"],
                            t["truth"],
                            t["reversal_date"] or "",
                            t["failure"],
                            t["scenario"],
                        ]
                    )
    with open(OUT / "expected_candidates.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "statement_id",
                "row_number",
                "txn_date",
                "amount_paise",
                "channel",
                "reference",
                "expected_label",
                "reversal_date",
                "is_true_failure",
                "scenario",
            ]
        )
        writer.writerows(labels)
    with open(OUT / "MANIFEST.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "statement_id",
                "bank",
                "layout_name",
                "date_range",
                "data_origin",
                "redacted_by",
                "checked_by",
                "pattern_scan_passed",
                "owner_consent",
            ]
        )
        writer.writerows(manifest)
    print(f"Wrote {len(manifest)} statements and {len(labels)} labelled debit rows to {OUT}")


if __name__ == "__main__":
    main()
