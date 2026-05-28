#!/usr/bin/env python3
"""Backward-compatible shim that forwards to the unified exporter.

Existing skill consumers (and anything pinned to this filename) keep working;
new work should use exporter.py directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from exporter import main  # noqa: E402


def _inject_codex_source(argv: list[str]) -> list[str]:
    if "--source" in argv:
        return argv
    if not argv:
        return argv
    head = [argv[0]]
    rest = argv[1:]
    return head + ["--source", "codex"] + rest


if __name__ == "__main__":
    raise SystemExit(main(_inject_codex_source(sys.argv[1:])))
