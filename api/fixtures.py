from typing import Any


def health_payload() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": "0.1.0-t1",
        "mode": "demo",
        "registry": {"loaded": 0, "verified": 0, "seeded": 0},
    }
