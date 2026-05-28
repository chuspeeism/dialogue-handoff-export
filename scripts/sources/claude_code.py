"""Claude Code source: reads ~/.claude/projects/<cwd-slug>/<session-id>.jsonl.

Claude Code stores each session as a JSONL file under
~/.claude/projects/{slugified-cwd}/{session-uuid}.jsonl. There is no central
SQLite index; we locate sessions by scanning project directories.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

from .base import ExporterError, Source


_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


def _claude_projects_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECTS_DIR", "~/.claude/projects")).expanduser()


def _timestamp_to_iso(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number > 10_000_000_000:
        number = number / 1000
    return dt.datetime.fromtimestamp(number).astimezone().isoformat(timespec="seconds")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ExporterError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
            event["_source_line"] = line_no
            events.append(event)
    return events


def _find_session_jsonl(session_id: str, root: Path) -> Path | None:
    """Scan all project dirs for `<session_id>.jsonl`."""
    if not root.exists():
        return None
    for project_dir in root.iterdir():
        if not project_dir.is_dir():
            continue
        candidate = project_dir / f"{session_id}.jsonl"
        if candidate.exists():
            return candidate
    return None


def _slug_to_cwd(slug: str) -> str:
    """Claude Code stores cwd as a slug like '-Users-sunyi-Tools-DeckLens'."""
    if slug.startswith("-"):
        return "/" + slug[1:].replace("-", "/")
    return slug


def _scan_thread_meta(events: list[dict[str, Any]], session_id: str) -> dict[str, Any]:
    """Pull title, cwd, timestamps, first-user-message preview from raw events."""
    title = ""
    cwd = ""
    first_user_text = ""
    first_ts = ""
    last_ts = ""

    for event in events:
        kind = event.get("type")
        ts = event.get("timestamp") or ""
        if ts:
            if not first_ts:
                first_ts = ts
            last_ts = ts

        if kind == "ai-title" and event.get("aiTitle"):
            title = event["aiTitle"]
            continue
        if kind == "user" and not first_user_text:
            content = (event.get("message") or {}).get("content")
            text = _extract_user_text(content)
            if text and not _is_system_reminder(text):
                first_user_text = text
        if kind in ("user", "assistant") and not cwd and event.get("cwd"):
            cwd = event["cwd"]

    if not title and first_user_text:
        title = first_user_text.splitlines()[0][:80]

    return {
        "id": session_id,
        "title": title or session_id,
        "cwd": cwd,
        "created_at": first_ts,
        "updated_at": last_ts,
        "preview": first_user_text[:200],
    }


def _extract_user_text(content: Any) -> str:
    """User message content can be a string OR a list with text/tool_result blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    parts.append(str(item["text"]))
                elif "text" in item and item["type"] != "tool_result":
                    parts.append(str(item["text"]))
        return "\n\n".join(p for p in parts if p)
    return ""


def _is_system_reminder(text: str) -> bool:
    """The harness wraps reminders in <system-reminder>...</system-reminder>.

    A user message can be entirely a reminder, or text + reminder appended.
    Treat as 'system reminder noise' only when the WHOLE message is wrapped.
    """
    stripped = text.strip()
    return stripped.startswith("<system-reminder>") and stripped.endswith("</system-reminder>")


def _strip_trailing_system_reminders(text: str) -> str:
    """Remove `<system-reminder>...</system-reminder>` blocks from message tail."""
    pattern = re.compile(r"\n*<system-reminder>.*?</system-reminder>\s*$", re.S)
    while True:
        new = pattern.sub("", text)
        if new == text:
            return new.rstrip()
        text = new


def _strip_command_envelopes(text: str) -> str:
    """Strip slash-command tool envelopes that the harness injects.

    Claude Code wraps user-typed slash commands like:
      <command-name>/foo</command-name><command-message>...</command-message>...
      <local-command-stdout>...</local-command-stdout>
    Keep the rest of the user's actual message.
    """
    text = re.sub(r"<command-name>.*?</command-name>", "", text, flags=re.S)
    text = re.sub(r"<command-message>.*?</command-message>", "", text, flags=re.S)
    text = re.sub(r"<command-args>.*?</command-args>", "", text, flags=re.S)
    text = re.sub(r"<local-command-stdout>.*?</local-command-stdout>", "", text, flags=re.S)
    return text.strip()


class ClaudeCodeSource(Source):
    name = "claude-code"
    label = "Claude Code"

    def can_handle_id(self, identifier: str) -> bool:
        return bool(_UUID_RE.match(identifier))

    def find_current(self) -> dict[str, Any]:
        session_id = (os.environ.get("CLAUDE_CODE_SESSION_ID") or "").strip()
        if not session_id:
            raise ExporterError(
                "Could not identify the current Claude Code session. "
                "Run inside Claude Code, or use --session-id ID / --rollout PATH."
            )
        return self.find_by_id(session_id)

    def find_by_id(self, identifier: str) -> dict[str, Any]:
        path = _find_session_jsonl(identifier, _claude_projects_root())
        if not path:
            raise ExporterError(
                f"Could not find Claude Code session {identifier}. "
                "Use --rollout /path/to/<id>.jsonl if you have the raw file."
            )
        thread = self.find_by_rollout(path, fallback_id=identifier)
        thread["lookup"] = "projects_scan"
        return thread

    def find_by_rollout(self, path: Path, fallback_id: str = "") -> dict[str, Any]:
        path = path.expanduser()
        if not path.exists():
            raise ExporterError(f"Session JSONL does not exist: {path}")

        session_id = fallback_id or path.stem
        events = _read_jsonl(path)
        meta = _scan_thread_meta(events, session_id)

        if not meta.get("cwd"):
            project_slug = path.parent.name
            meta["cwd"] = _slug_to_cwd(project_slug)

        return {
            "id": meta["id"],
            "title": meta["title"],
            "cwd": meta["cwd"],
            "rollout_path": str(path),
            "created_at": _timestamp_to_iso(meta["created_at"]) or _timestamp_to_iso(path.stat().st_ctime),
            "updated_at": _timestamp_to_iso(meta["updated_at"]) or _timestamp_to_iso(path.stat().st_mtime),
            "preview": meta["preview"],
            "lookup": "rollout_file",
        }

    def iter_canonical_events(self, thread: dict[str, Any]) -> Iterable[dict[str, Any]]:
        """Translate Claude Code events to the canonical schema.

        Claude Code event landscape (only message-bearing types matter here):

        - type=user, message.content = str | [{type:text, text}, {type:tool_result, ...}]
        - type=assistant, message.content = [{type:text, text}, {type:tool_use, name, input, id}]
        """
        path = Path(thread["rollout_path"])
        events = _read_jsonl(path)
        tool_use_names: dict[str, str] = {}

        for event in events:
            kind = event.get("type")
            line_no = event.get("_source_line")
            ts = event.get("timestamp") or ""

            if kind == "user":
                yield from _yield_user_event(event, line_no, ts, tool_use_names)
                continue

            if kind == "assistant":
                yield from _yield_assistant_event(event, line_no, ts, tool_use_names)
                continue
            # ai-title, system, file-history-snapshot, attachment(skill_listing),
            # permission-mode, queued_command, last-prompt, task_reminder,
            # queue-operation, message — all skipped.


def _yield_user_event(
    event: dict[str, Any],
    line_no: int,
    ts: str,
    tool_use_names: dict[str, str],
):
    message = event.get("message") or {}
    content = message.get("content")

    if isinstance(content, list):
        emitted_text = False
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "tool_result":
                call_id = item.get("tool_use_id") or f"call-{line_no}"
                output = item.get("content")
                if isinstance(output, list):
                    parts = []
                    for piece in output:
                        if isinstance(piece, dict) and piece.get("type") == "text":
                            parts.append(str(piece.get("text", "")))
                        elif isinstance(piece, str):
                            parts.append(piece)
                    output_text = "\n".join(parts)
                else:
                    output_text = str(output or "")
                yield {
                    "kind": "function_call_output",
                    "call_id": call_id,
                    "name": tool_use_names.get(call_id, "tool"),
                    "output": output_text,
                    "timestamp": ts,
                    "source_line": line_no,
                }
            elif item_type == "text" and item.get("text"):
                if emitted_text:
                    continue
                emitted_text = True
                text = str(item["text"])
                yield from _yield_user_text(text, line_no, ts)
        return

    if isinstance(content, str) and content.strip():
        yield from _yield_user_text(content, line_no, ts)


def _yield_user_text(text: str, line_no: int, ts: str):
    if _is_system_reminder(text):
        yield {
            "kind": "message",
            "role": "user",
            "phase": "",
            "text": text,
            "timestamp": ts,
            "source_line": line_no,
            "skip_reason": "system_reminder",
        }
        return
    cleaned = _strip_trailing_system_reminders(text)
    cleaned = _strip_command_envelopes(cleaned)
    yield {
        "kind": "message",
        "role": "user",
        "phase": "",
        "text": cleaned,
        "timestamp": ts,
        "source_line": line_no,
        "skip_reason": None if cleaned else "other_role",
    }


def _yield_assistant_event(
    event: dict[str, Any],
    line_no: int,
    ts: str,
    tool_use_names: dict[str, str],
):
    message = event.get("message") or {}
    content = message.get("content")
    if not isinstance(content, list):
        if isinstance(content, str) and content.strip():
            yield {
                "kind": "message",
                "role": "assistant",
                "phase": "",
                "text": content,
                "timestamp": ts,
                "source_line": line_no,
                "skip_reason": None,
            }
        return

    text_parts: list[str] = []
    pending_tool_uses: list[dict[str, Any]] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "text" and item.get("text"):
            text_parts.append(str(item["text"]))
        elif item_type == "tool_use":
            call_id = item.get("id") or f"call-{line_no}"
            name = item.get("name") or "tool"
            tool_use_names[call_id] = name
            pending_tool_uses.append(
                {
                    "kind": "function_call",
                    "call_id": call_id,
                    "name": name,
                    "arguments": item.get("input"),
                    "timestamp": ts,
                    "source_line": line_no,
                }
            )

    if text_parts:
        yield {
            "kind": "message",
            "role": "assistant",
            "phase": "",
            "text": "\n\n".join(text_parts),
            "timestamp": ts,
            "source_line": line_no,
            "skip_reason": None,
        }
    yield from pending_tool_uses
