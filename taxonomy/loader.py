from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import TaxonomyCatalog, TaxonomyClaimType


class TaxonomyError(ValueError):
    pass


def load_taxonomy(directory: Path | None = None) -> TaxonomyCatalog:
    root = directory or Path(__file__).resolve().parent / "claim_types"
    entries: dict[str, TaxonomyClaimType] = {}
    for path in sorted(root.glob("*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            entry = TaxonomyClaimType.model_validate(payload)
        except (OSError, yaml.YAMLError, ValidationError, TypeError) as exc:
            raise TaxonomyError(f"Invalid taxonomy file {path}: {exc}") from exc
        if entry.id in entries:
            raise TaxonomyError(f"Duplicate claim type: {entry.id}")
        if entry.rule_id is not None and not entry.rule_id.startswith("R-"):
            raise TaxonomyError(f"{entry.id}: rule_id must use R-000 format")
        entries[entry.id] = entry
    if not entries:
        raise TaxonomyError(f"No claim types found in {root}")
    return TaxonomyCatalog(entries)
