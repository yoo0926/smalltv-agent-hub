#!/usr/bin/env python3
"""Reject local runtime/build data and common machine-specific secrets in Git."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve().relative_to(ROOT).as_posix()
FORBIDDEN_PARTS = {
    ".runtime",
    "references",
    "tmp",
    ".pio",
    ".pio-core",
    ".venv",
    "dist",
}
FORBIDDEN_SUFFIXES = {".bin", ".elf", ".map"}
CONTENT_PATTERNS = (
    ("absolute macOS user path", re.compile(rb"/Users/[A-Za-z0-9._-]+/")),
    ("GitHub token", re.compile(rb"\b(?:ghp|github_pat)_[A-Za-z0-9_]{20,}\b")),
    ("Slack token", re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("AWS access key", re.compile(rb"\bAKIA[0-9A-Z]{16}\b")),
)


def candidate_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        check=True,
    )
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def main() -> int:
    problems: list[str] = []
    files = candidate_files()
    for name in files:
        path = Path(name)
        if any(part in FORBIDDEN_PARTS for part in path.parts):
            problems.append(f"local/build path selected for versioning: {name}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            problems.append(f"firmware/build binary selected for versioning: {name}")
        if name == SELF:
            continue
        data = (ROOT / path).read_bytes()
        for label, pattern in CONTENT_PATTERNS:
            if pattern.search(data):
                problems.append(f"{label}: {name}")

    if problems:
        print("Repository hygiene check failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print(f"Repository hygiene check passed ({len(files)} versioned candidates).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
