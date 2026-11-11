from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
AADHAAR = re.compile(r"(?<!\d)(?:\d[ -]?){12}(?!\d)")
ACCOUNT = re.compile(r"(?<!\d)\d{9,18}(?!\d)")
IGNORED = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}


def tracked_files() -> list[Path]:
    result = subprocess.run(["git", "ls-files"], check=True, capture_output=True, text=True)
    return [Path(line) for line in result.stdout.splitlines() if line]


def main() -> int:
    violations: list[str] = []
    files = tracked_files()
    for path in files:
        if any(part in IGNORED for part in path.parts) or path.as_posix().startswith("data/real/"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for label, pattern in (("PAN", PAN), ("Aadhaar", AADHAAR), ("account-number", ACCOUNT)):
            if pattern.search(text):
                violations.append(f"{label}: {path}")
    if violations:
        print("Sensitive-data guard failed:")
        print("\n".join(violations))
        return 1
    print(f"Sensitive-data guard passed for {len(files)} tracked files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
