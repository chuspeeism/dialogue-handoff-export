"""Codex source: reads ~/.codex/state_*.sqlite + ~/.codex/sessions/**/rollout-*.jsonl."""

from __future__ import annotations

import datetime as dt
import glob
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .base import ExporterError, Source


def _codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()


def _timestamp_to_iso(value: Any) -> str:
    if value in (None, ""):
        return ""
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


def _find_state_db(home: Path) -> Path | None:
    explicit = os.environ.get("CODEX_STATE_DB")
    if explicit:
        path = Path(explicit).expanduser()
        if path.exists():
            return path
    candidates = sorted(home.glob("state_*.sqlite"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _sqlite_uri(path: Path) -> str:
    return f"file:{path}?mode=ro"


def _title_from_state(thread_id: str, home: Path) -> str:
    if not thread_id:
        return ""
    db_path = _find_state_db(home)
    if not db_path:
        return ""
    try:
        conn = sqlite3.connect(_sqlite_uri(db_path), uri=True)
        row = conn.execute("select title from threads where id = ?", (thread_id,)).fetchone()
        conn.close()
    except sqlite3.Error:
        return ""
    return row[0] if row and row[0] else ""


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and "text" in item:
            parts.append(str(item["text"]))
        elif isinstance(item, str):
            parts.append(item)
    return "\n\n".join(part for part in parts if part)


def _is_environment_context(text: str) -> bool:
    stripped = text.strip()
    return stripped.startswith("<environment_context>") and "</environment_context>" in stripped


def _parse_json_maybe(value: str) -> Any:
    try:
        return json.loads(value)
    except Exception:
        return value


_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)


class CodexSource(Source):
    name = "codex"
    label = "Codex"

    def can_handle_id(self, identifier: str) -> bool:
        return bool(_UUID_RE.match(identifier))

    def find_current(self) -> dict[str, Any]:
        thread_id = os.environ.get("CODEX_THREAD_ID", "").strip()
        if not thread_id:
            raise ExporterError(
                "Could not identify the current Codex thread. "
                "Run inside Codex Desktop, or use --thread-id THREAD_ID / --rollout PATH."
            )
        return self.find_by_id(thread_id)

    def find_by_id(self, identifier: str) -> dict[str, Any]:
        home = _codex_home()
        row: dict[str, Any] | None = None
        db_path = _find_state_db(home)

        if db_path and db_path.exists():
            try:
                conn = sqlite3.connect(_sqlite_uri(db_path), uri=True)
                conn.row_factory = sqlite3.Row
                try:
                    rows = conn.execute(
                        """
                        select
                          id, title, cwd, rollout_path, created_at, updated_at,
                          created_at_ms, updated_at_ms, preview
                        from threads
                        where id = ?
                        """,
                        (identifier,),
                    ).fetchall()
                finally:
                    conn.close()
                if rows:
                    sqlite_row = rows[0]
                    row = {key: sqlite_row[key] for key in sqlite_row.keys()}
            except sqlite3.Error:
                row = None

        if row:
            rollout_path = Path(row.get("rollout_path") or "").expanduser()
            if rollout_path.exists():
                return {
                    "id": row.get("id") or identifier,
                    "title": row.get("title") or row.get("preview") or identifier,
                    "cwd": row.get("cwd") or "",
                    "rollout_path": str(rollout_path),
                    "created_at": _timestamp_to_iso(row.get("created_at_ms") or row.get("created_at")),
                    "updated_at": _timestamp_to_iso(row.get("updated_at_ms") or row.get("updated_at")),
                    "preview": row.get("preview") or "",
                    "lookup": "state_sqlite",
                }

        matches = glob.glob(str(home / "sessions" / "**" / f"*{identifier}*.jsonl"), recursive=True)
        if matches:
            rollout = Path(matches[0])
            return self.find_by_rollout(rollout, fallback_id=identifier) | {"lookup": "rollout_glob"}

        raise ExporterError(
            f"Could not find Codex thread {identifier}. "
            "Use --rollout /path/to/rollout.jsonl if you have the raw file."
        )

    def find_by_rollout(self, path: Path, fallback_id: str = "") -> dict[str, Any]:
        path = path.expanduser()
        if not path.exists():
            raise ExporterError(f"Rollout file does not exist: {path}")

        thread: dict[str, Any] = {
            "id": fallback_id,
            "title": path.stem,
            "cwd": "",
            "rollout_path": str(path),
            "created_at": _timestamp_to_iso(path.stat().st_ctime),
            "updated_at": _timestamp_to_iso(path.stat().st_mtime),
            "preview": "",
            "lookup": "rollout_file",
        }

        for event in _read_jsonl(path):
            if event.get("type") != "session_meta":
                continue
            payload = event.get("payload") or {}
            thread["id"] = payload.get("id") or fallback_id or thread["id"]
            thread["cwd"] = payload.get("cwd") or thread["cwd"]
            thread["created_at"] = (
                payload.get("timestamp") or event.get("timestamp") or thread["created_at"]
            )
            break

        title = _title_from_state(thread.get("id") or "", _codex_home())
        if title:
            thread["title"] = title
        return thread

    def iter_canonical_events(self, thread: dict[str, Any]) -> Iterable[dict[str, Any]]:
        rollout_path = Path(thread["rollout_path"])
        events = _read_jsonl(rollout_path)

        for event in events:
            if event.get("type") != "response_item":
                continue
            payload = event.get("payload") or {}
            line_no = event.get("_source_line")
            payload_type = payload.get("type")
            timestamp = event.get("timestamp") or ""

            if payload_type == "message":
                role = payload.get("role") or ""
                text = _extract_text(payload.get("content"))
                skip_reason = None
                if role == "developer":
                    skip_reason = "developer"
                elif role == "user" and _is_environment_context(text):
                    skip_reason = "environment_context"
                elif role not in ("user", "assistant"):
                    skip_reason = "other_role"
                yield {
                    "kind": "message",
                    "role": role,
                    "phase": payload.get("phase") or "",
                    "text": text,
                    "timestamp": timestamp,
                    "source_line": line_no,
                    "skip_reason": skip_reason,
                }
                continue

            if payload_type == "function_call":
                yield {
                    "kind": "function_call",
                    "call_id": payload.get("call_id") or f"call-{line_no}",
                    "name": payload.get("name") or "tool",
                    "arguments": _parse_json_maybe(payload.get("arguments") or ""),
                    "timestamp": timestamp,
                    "source_line": line_no,
                }
                continue

            if payload_type == "function_call_output":
                yield {
                    "kind": "function_call_output",
                    "call_id": payload.get("call_id") or f"call-{line_no}",
                    "name": "",
                    "output": payload.get("output") or "",
                    "timestamp": timestamp,
                    "source_line": line_no,
                }
                continue

            if payload_type == "reasoning":
                yield {
                    "kind": "reasoning",
                    "source_line": line_no,
                    "timestamp": timestamp,
                }
