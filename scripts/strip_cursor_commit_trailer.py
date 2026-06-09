#!/usr/bin/env python3
"""
Remove the line ``Made-with: Cursor`` from git commit messages.

- Stdin → stdout: for ``git filter-branch --msg-filter``.
- One argument (file path): rewrite that file in place (for commit-msg hook).
"""
from __future__ import annotations

import sys
from pathlib import Path

_TRAILER = b"Made-with: Cursor"


def strip_message(data: bytes) -> bytes:
    lines = [ln for ln in data.splitlines() if ln.strip() != _TRAILER]
    return b"\n".join(lines).rstrip() + b"\n"


def main() -> int:
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        path.write_bytes(strip_message(path.read_bytes()))
        return 0
    sys.stdout.buffer.write(strip_message(sys.stdin.buffer.read()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
