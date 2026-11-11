from typing import Any

from .schemas import RegistrySummary

REGISTRY_SUMMARY = [
    RegistrySummary(
        id="R-001",
        name="UPI debit without beneficiary credit",
        status="Seeded",
        confidence="Low",
    ),
    RegistrySummary(
        id="R-007",
        name="Payment due to micro or small supplier",
        status="Seeded",
        confidence="Low",
    ),
]


def health_payload() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": "0.1.0-t0",
        "mode": "demo",
        "registry": {"loaded": 0, "verified": 0, "seeded": 0, "note": "T1 loader pending"},
    }
