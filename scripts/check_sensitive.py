from __future__ import annotations

import csv
import io
import re
import subprocess
import sys
from pathlib import Path

PAN = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
AADHAAR = re.compile(r"\b\d{4} \d{4} \d{4}\b")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"\b[6-9]\d{9}\b")
ACCOUNT = re.compile(r"(?<!/)\b\d{9,18}\b(?!/)")
IGNORED = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}


def tracked_files() -> list[Path]:
    result = subprocess.run(["git", "ls-files"], check=True, capture_output=True, text=True)
    return [Path(line) for line in result.stdout.splitlines() if line]


def scan_text(text: str, path: Path) -> list[str]:
    if path.name == "expected_candidates.csv":
        rows = csv.DictReader(io.StringIO(text))
        text = "\n".join(
            ",".join(value for key, value in row.items() if key != "reference") for row in rows
        )
    scrubbed = re.sub(r"/\d{12}/", "/REF/", text)
    patterns = (
        ("PAN", PAN),
        ("Aadhaar", AADHAAR),
        ("email", EMAIL),
        ("phone", PHONE),
        ("account-number", ACCOUNT),
    )
    return [label for label, pattern in patterns if pattern.search(scrubbed)]


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
        for label in scan_text(text, path):
            violations.append(f"{label}: {path}")
    if violations:
        print("Sensitive-data guard failed:")
        print("\n".join(violations))
        return 1
    print(f"Sensitive-data guard passed for {len(files)} tracked files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
