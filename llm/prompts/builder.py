from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parent


def load_category_definitions(path: Path | None = None) -> dict[str, str]:
    config_path = path or ROOT / "categories.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    categories = payload.get("categories")
    if not isinstance(categories, dict) or not categories:
        raise ValueError("prompt category configuration must contain categories")
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in categories.items()):
        raise ValueError("prompt category definitions must map strings to strings")
    return categories


def build_prompt(version: str, email: str, *, category_config: Path | None = None) -> str:
    if version not in {"triage_v1", "extract_v1"}:
        raise ValueError(f"unsupported prompt version: {version}")
    template = (ROOT / f"{version}.txt").read_text(encoding="utf-8")
    definitions = "\n".join(f"- {key}: {value}" for key, value in load_category_definitions(category_config).items())
    return template.replace("{{CATEGORY_DEFINITIONS}}", definitions).replace("{{EMAIL}}", email)


__all__ = ["build_prompt", "load_category_definitions"]
