from __future__ import annotations

from pathlib import Path

from cases.models import Case
from taxonomy.loader import load_taxonomy


ROOT = Path(__file__).resolve().parents[1]


def build_claim_pack(case: Case) -> dict[str, object]:
    spec = load_taxonomy().get(case.claim_type)
    template_path = ROOT / "claims" / "templates" / spec.template
    template = template_path.read_text(encoding="utf-8") if template_path.exists() else ""
    amount = f"₹{case.amount_paise / 100:,.2f}" if case.amount_paise is not None else "the amount shown in the attached records"
    rule_note = (
        f"The linked rule is {case.rule_id} and is marked {case.rule_status}."
        if case.rule_id
        else "No verified registry rule is linked yet; this pack is evidence-first and does not assert a deadline or compensation amount."
    )
    draft = template.format(
        amount=amount,
        reference=case.reference or "not extracted",
        status=case.status,
        rule_note=rule_note,
    )
    return {
        "case_id": case.case_id,
        "claim_type": case.claim_type,
        "draft": draft,
        "evidence_checklist": spec.evidence,
        "escalation": spec.escalation,
        "rule_id": case.rule_id,
        "rule_status": case.rule_status,
        "deadline": case.deadline.isoformat() if case.deadline else None,
        "days_overdue": case.days_overdue,
    }
