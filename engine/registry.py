from __future__ import annotations

import argparse

from .registry_loader import load_registry, validate_entry_for_ci


def check_registry() -> int:
    registry = load_registry()
    print("ID     STATUS    CONFIDENCE  UNRESOLVED FIELDS")
    print("-----  --------  ----------  -----------------")
    for entry in registry.all():
        unresolved = ", ".join(entry.unresolved_fields()) or "-"
        print(f"{entry.id:<5}  {entry.status:<8}  {entry.confidence:<10}  {unresolved}")
    errors = [
        f"{entry.id}: {error}"
        for entry in registry.all()
        for error in validate_entry_for_ci(entry)
    ]
    if errors:
        print("\nCI validation errors:")
        print("\n".join(errors))
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect the Haq Rights Registry")
    parser.add_argument("command", choices=["check"], help="registry operation")
    args = parser.parse_args()
    if args.command == "check":
        return check_registry()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
