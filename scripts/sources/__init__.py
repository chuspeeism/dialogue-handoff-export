"""Source registry."""

from .base import ExporterError, Source
from .claude_code import ClaudeCodeSource
from .codex import CodexSource

SOURCES: dict[str, Source] = {
    "codex": CodexSource(),
    "claude-code": ClaudeCodeSource(),
}


def get_source(name: str) -> Source:
    if name not in SOURCES:
        raise ExporterError(
            f"Unknown source '{name}'. Valid: {', '.join(sorted(SOURCES.keys()))}"
        )
    return SOURCES[name]


def auto_detect_source() -> str:
    """Best-effort detection of which AI runtime is invoking us right now."""
    import os

    if os.environ.get("CLAUDE_CODE_SESSION_ID") or os.environ.get("CLAUDECODE"):
        return "claude-code"
    if os.environ.get("CODEX_THREAD_ID"):
        return "codex"
    raise ExporterError(
        "Could not auto-detect source. Pass --source codex or --source claude-code, "
        "or supply --thread-id / --session-id / --rollout."
    )


__all__ = ["ExporterError", "Source", "SOURCES", "get_source", "auto_detect_source"]
