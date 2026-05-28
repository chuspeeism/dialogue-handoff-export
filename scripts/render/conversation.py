"""Conversation normalization + markdown renderers (transcript + handoff)."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any, Iterable


APP_VERSION = "0.2.0"
VALID_MODES = ("share", "with-tools", "raw-archive")
DEFAULT_TOOL_OUTPUT_CHARS = 1800


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def compact_text(value: str, limit: int = DEFAULT_TOOL_OUTPUT_CHARS) -> str:
    value = value.strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + f"\n...[truncated {len(value) - limit} chars]"


def normalize_conversation(
    source_name: str,
    source_label: str,
    thread: dict[str, Any],
    canonical_events: Iterable[dict[str, Any]],
    mode: str,
    tool_output_chars: int = DEFAULT_TOOL_OUTPUT_CHARS,
) -> dict[str, Any]:
    """Convert canonical events from a Source into the export bundle dict."""
    messages: list[dict[str, Any]] = []
    tool_events: list[dict[str, Any]] = []
    raw_events: list[dict[str, Any]] = []
    skipped = {
        "developer_messages": 0,
        "environment_context_messages": 0,
        "system_reminder_messages": 0,
        "reasoning_events": 0,
        "raw_events_omitted": 0,
    }

    call_names: dict[str, str] = {}
    canonical_events = list(canonical_events)

    for event in canonical_events:
        kind = event["kind"]
        line_no = event.get("source_line")

        if kind == "message":
            skip_reason = event.get("skip_reason")
            if skip_reason == "developer":
                skipped["developer_messages"] += 1
                continue
            if skip_reason == "environment_context":
                skipped["environment_context_messages"] += 1
                continue
            if skip_reason == "system_reminder":
                skipped["system_reminder_messages"] += 1
                continue
            if skip_reason == "other_role":
                continue
            messages.append(
                {
                    "id": f"msg-{line_no}",
                    "role": event["role"],
                    "type": "message",
                    "phase": event.get("phase") or "",
                    "content": event.get("text") or "",
                    "content_format": "markdown",
                    "timestamp": event.get("timestamp") or "",
                    "source_line": line_no,
                }
            )
            continue

        if kind == "function_call":
            call_id = event.get("call_id") or f"call-{line_no}"
            call_names[call_id] = event.get("name") or "tool"
            if mode in ("with-tools", "raw-archive"):
                tool_events.append(
                    {
                        "id": f"tool-{line_no}",
                        "kind": "function_call",
                        "call_id": call_id,
                        "name": call_names[call_id],
                        "arguments": event.get("arguments"),
                        "timestamp": event.get("timestamp") or "",
                        "source_line": line_no,
                    }
                )
            continue

        if kind == "function_call_output":
            call_id = event.get("call_id") or f"call-{line_no}"
            output = event.get("output") or ""
            if mode in ("with-tools", "raw-archive"):
                tool_events.append(
                    {
                        "id": f"tool-{line_no}",
                        "kind": "function_call_output",
                        "call_id": call_id,
                        "name": event.get("name") or call_names.get(call_id, "tool"),
                        "output": output if mode == "raw-archive" else compact_text(output, tool_output_chars),
                        "timestamp": event.get("timestamp") or "",
                        "source_line": line_no,
                    }
                )
            continue

        if kind == "reasoning":
            skipped["reasoning_events"] += 1

    if mode == "raw-archive":
        raw_events = canonical_events
    else:
        skipped["raw_events_omitted"] = len(canonical_events)

    return {
        "version": APP_VERSION,
        "source": source_name,
        "source_label": source_label,
        "mode": mode,
        "exported_at": now_iso(),
        "thread": thread,
        "messages": messages,
        "tool_events": tool_events,
        "raw_events": raw_events,
        "skipped": skipped,
    }


def message_heading(role: str) -> str:
    return "User" if role == "user" else "Assistant"


def render_message_markdown(message: dict[str, Any], index: int) -> str:
    phase = message.get("phase")
    phase_note = f" ({phase})" if phase else ""
    return (
        f"### {index}. {message_heading(message['role'])}{phase_note}\n\n"
        f"{message.get('content', '').rstrip()}\n"
    )


def render_tool_markdown(tool_events: list[dict[str, Any]]) -> str:
    if not tool_events:
        return ""
    lines = ["\n## 工具调用摘要\n"]
    for event in tool_events:
        label = "调用" if event["kind"] == "function_call" else "结果"
        lines.append(f"### {label}: {event.get('name', 'tool')}\n")
        if event["kind"] == "function_call":
            args = event.get("arguments")
            args_text = json.dumps(args, ensure_ascii=False, indent=2) if not isinstance(args, str) else args
            lines.append("```json\n" + args_text.rstrip() + "\n```\n")
        else:
            lines.append("```text\n" + str(event.get("output", "")).rstrip() + "\n```\n")
    return "\n".join(lines)


def render_conversation_md(data: dict[str, Any]) -> str:
    thread = data["thread"]
    source_label = data.get("source_label", data.get("source", ""))
    lines = [
        f"# {thread.get('title') or f'{source_label} Conversation'}",
        "",
        "## 元信息",
        "",
        f"- 来源：{source_label}",
        f"- 会话 ID：{thread.get('id', '')}",
        f"- 工作目录：{thread.get('cwd', '')}",
        f"- 原始记录：{thread.get('rollout_path', '')}",
        f"- 导出模式：{data.get('mode', '')}",
        f"- 导出时间：{data.get('exported_at', '')}",
        "",
        "## 对话记录",
        "",
    ]
    for index, message in enumerate(data["messages"], 1):
        lines.append(render_message_markdown(message, index))
    if data["tool_events"]:
        lines.append(render_tool_markdown(data["tool_events"]))
    return "\n".join(lines).rstrip() + "\n"


def render_handoff_md(data: dict[str, Any]) -> str:
    thread = data["thread"]
    source_label = data.get("source_label", data.get("source", ""))
    lines = [
        "# AI 对话接力包",
        "",
        "你将接手以下对话。请先理解已有上下文，然后从最后一个用户问题或最后一个未完成任务继续。",
        "",
        "请基于以下完整对话继续，不要要求用户重复已经提供过的信息。",
        "",
        "## 来源信息",
        "",
        f"- 来源：{source_label}",
        f"- 标题：{thread.get('title') or f'{source_label} Conversation'}",
        f"- 会话 ID：{thread.get('id', '')}",
        f"- 导出时间：{data.get('exported_at', '')}",
        "",
        "## 完整对话",
        "",
    ]
    for index, message in enumerate(data["messages"], 1):
        lines.append(render_message_markdown(message, index))
    if data["tool_events"]:
        lines.append(render_tool_markdown(data["tool_events"]))
    return "\n".join(lines).rstrip() + "\n"
