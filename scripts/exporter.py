#!/usr/bin/env python3
"""Unified dialogue handoff exporter.

Supports multiple AI conversation sources via a Source plugin in
`sources/`. Today: Codex (and Claude Code, added in stage 2).

Usage:

  exporter.py export-current [--source codex|claude-code] [--mode share|...] [--output ./exports]
  exporter.py export --thread-id ID  [--source codex] ...
  exporter.py export --session-id ID [--source claude-code] ...
  exporter.py export --rollout PATH  ...
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

from render import (
    DEFAULT_TOOL_OUTPUT_CHARS,
    VALID_MODES,
    normalize_conversation,
    render_conversation_md,
    render_handoff_md,
    render_html,
)
from sources import (
    ExporterError,
    SOURCES,
    auto_detect_source,
    get_source,
)


def _safe_slug(value: str, fallback: str = "conversation") -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|\n\r\t]+", "_", value).strip(" ._")
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned[:80] or fallback


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _export_data(data: dict[str, Any], output_root: Path) -> Path:
    thread = data["thread"]
    title = _safe_slug(thread.get("title") or "conversation")
    day = dt.datetime.now().astimezone().strftime("%Y-%m-%d")
    short_id = (thread.get("id") or "noid")[:8]
    source = data.get("source", "")
    export_dir = output_root / f"{day}_{source}_{title}_{short_id}_{data.get('mode', 'share')}"
    export_dir.mkdir(parents=True, exist_ok=True)

    conversation_md = render_conversation_md(data)
    handoff_md = render_handoff_md(data)
    conversation_html = render_html(data, handoff_md)

    _write_json(export_dir / "conversation.raw.json", data)
    _write_text(export_dir / "conversation.md", conversation_md)
    _write_text(export_dir / "ai-handoff.md", handoff_md)
    _write_text(export_dir / "conversation.html", conversation_html)
    return export_dir


def _resolve_source(args: argparse.Namespace) -> str:
    explicit = getattr(args, "source", None)
    if explicit and explicit != "auto":
        return explicit
    return auto_detect_source()


def _build_from_thread(source_name: str, identifier: str, args: argparse.Namespace) -> Path:
    source = get_source(source_name)
    thread = source.find_by_id(identifier)
    return _build_from_thread_dict(source, thread, args)


def _build_from_current(source_name: str, args: argparse.Namespace) -> Path:
    source = get_source(source_name)
    thread = source.find_current()
    return _build_from_thread_dict(source, thread, args)


def _build_from_rollout(source_name: str, rollout: Path, args: argparse.Namespace) -> Path:
    source = get_source(source_name)
    thread = source.find_by_rollout(rollout)
    return _build_from_thread_dict(source, thread, args)


def _build_from_thread_dict(source, thread: dict[str, Any], args: argparse.Namespace) -> Path:
    events = source.iter_canonical_events(thread)
    data = normalize_conversation(
        source_name=source.name,
        source_label=source.label,
        thread=thread,
        canonical_events=events,
        mode=args.mode,
        tool_output_chars=args.tool_output_chars,
    )
    return _export_data(data, Path(args.output).expanduser())


def _print_success(export_dir: Path, source_label: str) -> None:
    files = ["conversation.raw.json", "conversation.md", "ai-handoff.md", "conversation.html"]
    print(f"已导出 {source_label} 对话：")
    print(export_dir)
    for name in files:
        print(f"  {name}")


def _add_common_export_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source",
        choices=["auto"] + sorted(SOURCES.keys()),
        default="auto",
        help="对话来源；auto 会根据环境变量推断",
    )
    parser.add_argument("--mode", choices=VALID_MODES, default="share", help="导出模式")
    parser.add_argument("--output", default="exports", help="导出目录，默认 exports")
    parser.add_argument(
        "--tool-output-chars",
        type=int,
        default=DEFAULT_TOOL_OUTPUT_CHARS,
        help="with-tools 模式下单个工具输出摘要的最大字符数",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="exporter.py",
        description="Export one explicitly targeted AI conversation as Markdown, HTML, and JSON.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    current = subparsers.add_parser("export-current", help="导出当前对话窗口")
    _add_common_export_args(current)

    export = subparsers.add_parser("export", help="通过会话 id 或 rollout 文件导出指定对话")
    target = export.add_mutually_exclusive_group(required=True)
    target.add_argument("--thread-id", help="Codex thread id")
    target.add_argument("--session-id", help="Claude Code session id (UUID)")
    target.add_argument("--rollout", help="JSONL 原始记录路径 (Codex rollout / Claude Code session jsonl)")
    _add_common_export_args(export)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "export-current":
            source_name = _resolve_source(args)
            export_dir = _build_from_current(source_name, args)
        elif args.command == "export":
            if args.rollout:
                source_name = _resolve_source(args)
                export_dir = _build_from_rollout(source_name, Path(args.rollout), args)
            else:
                identifier = args.thread_id or args.session_id
                if args.source == "auto":
                    if args.thread_id:
                        source_name = "codex"
                    elif args.session_id:
                        source_name = "claude-code"
                    else:
                        source_name = auto_detect_source()
                else:
                    source_name = args.source
                export_dir = _build_from_thread(source_name, identifier, args)
        else:
            parser.error("Unknown command")
            return 2
    except ExporterError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    label = get_source(source_name).label
    _print_success(export_dir, label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
