"""Source interface + canonical event schema for the dialogue handoff exporter.

A Source knows how to:
1. Locate a single conversation (current / by id / by rollout file path).
2. Yield canonical events from that conversation.

Canonical event shapes:

  {"kind": "message", "role": "user"|"assistant", "phase": str,
   "text": str, "timestamp": str, "source_line": int|None,
   "skip_reason": None|"developer"|"environment_context"|"system_reminder"}

  {"kind": "function_call", "call_id": str, "name": str,
   "arguments": Any, "timestamp": str, "source_line": int|None}

  {"kind": "function_call_output", "call_id": str, "name": str,
   "output": str, "timestamp": str, "source_line": int|None}

  {"kind": "reasoning", "source_line": int|None}

Thread dict shape (returned by find_*):

  {"id": str, "title": str, "cwd": str, "rollout_path": str,
   "created_at": str, "updated_at": str, "preview": str,
   "lookup": str}  # lookup describes how it was located
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterable


class ExporterError(Exception):
    """User-facing error."""


class Source(ABC):
    name: str  # "codex" | "claude_code"
    label: str  # human-friendly: "Codex" | "Claude Code"

    @abstractmethod
    def find_current(self) -> dict[str, Any]:
        """Locate the currently-running conversation. Raises ExporterError if it can't."""

    @abstractmethod
    def find_by_id(self, identifier: str) -> dict[str, Any]:
        """Locate a conversation by its source-specific id (thread id / session id)."""

    @abstractmethod
    def find_by_rollout(self, path: Path) -> dict[str, Any]:
        """Build a thread descriptor from a raw rollout/jsonl file path."""

    @abstractmethod
    def iter_canonical_events(
        self, thread: dict[str, Any]
    ) -> Iterable[dict[str, Any]]:
        """Yield canonical events for the given thread."""

    def can_handle_id(self, identifier: str) -> bool:
        """Heuristic used by --source auto. Subclasses may override."""
        return False
