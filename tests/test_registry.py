from pathlib import Path

import pytest

from engine.registry_loader import RegistryGateError, load_registry


def test_all_seed_entries_load() -> None:
    registry = load_registry(Path("registry"))
    assert len(registry.all()) == 16
    assert registry.get("R-001").status == "Seeded"
    assert registry.get("R-016").status == "Parked"


def test_seeded_is_demo_only_and_parked_never_computes() -> None:
    registry = load_registry(Path("registry"))
    assert registry.computable("R-001", "demo").id == "R-001"
    with pytest.raises(RegistryGateError):
        registry.computable("R-001", "live")
    with pytest.raises(RegistryGateError):
        registry.computable("R-016", "demo")
    with pytest.raises(RegistryGateError):
        registry.computable("R-016", "live")


def test_unresolved_fields_are_visible() -> None:
    entry = load_registry(Path("registry")).get("R-001")
    unresolved = entry.unresolved_fields()
    assert "clock.weekends_count" in unresolved
    assert "verification.peer_checker" in unresolved
    assert "sources[0].url" in unresolved
