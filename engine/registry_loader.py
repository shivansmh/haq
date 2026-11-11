from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import ValidationError

from .models import RightEntry

Mode = Literal["demo", "live"]


class RegistryError(ValueError):
    """Raised when the machine-readable Rights Registry is invalid."""


class RegistryGateError(RegistryError):
    """Raised when a right is not allowed to compute in the requested mode."""


class Registry:
    def __init__(self, entries: dict[str, RightEntry]):
        self._entries = entries

    def all(self) -> list[RightEntry]:
        return [self._entries[key] for key in sorted(self._entries)]

    def get(self, right_id: str) -> RightEntry:
        try:
            return self._entries[right_id]
        except KeyError as exc:
            raise RegistryError(f"Unknown registry entry: {right_id}") from exc

    def computable(self, right_id: str, mode: Mode) -> RightEntry:
        entry = self.get(right_id)
        allowed = {"Verified"} if mode == "live" else {"Seeded", "Verified"}
        if entry.status not in allowed:
            raise RegistryGateError(
                f"{right_id} is {entry.status} and cannot compute in {mode} mode"
            )
        return entry


def load_registry(registry_dir: Path | None = None) -> Registry:
    directory = registry_dir or Path(__file__).resolve().parents[1] / "registry"
    entries: dict[str, RightEntry] = {}
    for path in sorted(directory.glob("R-*.yaml")):
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
            entry = RightEntry.model_validate(payload)
        except (OSError, yaml.YAMLError, ValidationError, TypeError) as exc:
            raise RegistryError(f"Invalid registry file {path}: {exc}") from exc
        if entry.id in entries:
            raise RegistryError(f"Duplicate registry ID: {entry.id}")
        entries[entry.id] = entry
    if not entries:
        raise RegistryError(f"No registry entries found in {directory}")
    return Registry(entries)


def validate_entry_for_ci(entry: RightEntry) -> list[str]:
    errors: list[str] = []
    if entry.status == "Verified":
        if not any(example.peer_checker for example in entry.worked_examples):
            errors.append("Verified entry needs a worked example with a named peer checker")
        if not any(source.tier <= 3 and source.clause and source.url for source in entry.sources):
            errors.append("Verified entry needs a tier 1-3 source with clause and URL")
        if entry.unresolved_fields():
            errors.append(f"Verified entry has unresolved fields: {entry.unresolved_fields()}")
    return errors
