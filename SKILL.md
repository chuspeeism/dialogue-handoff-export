---
name: dialogue-handoff-export
description: Export a single explicitly targeted AI conversation (Codex or Claude Code) as a dialogue handoff package. Use when the user asks to use 对话交接器, export/share the current conversation, 导出当前对话, 导出聊天记录, create an AI handoff markdown, produce a ChatGPT-like conversation replay HTML, or export by thread id / session id / JSONL file path. Do not use for listing recent conversations or searching chat history.
---

# Dialogue Handoff Export

Export exactly one conversation that the user explicitly targets. Do not list recent conversations, search historical conversations, or batch-export a project.

## Supported sources

- **Codex** — reads `~/.codex/state_*.sqlite` + `~/.codex/sessions/**/rollout-*.jsonl`. Identified by env `CODEX_THREAD_ID`.
- **Claude Code** — reads `~/.claude/projects/<cwd-slug>/<session-uuid>.jsonl`. Identified by env `CLAUDE_CODE_SESSION_ID`.

Valid inputs:

1. Current conversation window (whichever AI runtime is invoking the script).
2. A Codex thread id supplied by the user.
3. A Claude Code session id (UUID) supplied by the user.
4. A rollout/session `*.jsonl` path supplied by the user.

## Quick Start

Resolve `scripts/exporter.py` relative to this `SKILL.md`, then run it from the user's current workspace so the `exports/` folder lands near the user's work.

Default command for the current conversation (auto-detects Codex vs Claude Code):

```bash
python3 /path/to/dialogue-handoff-export/scripts/exporter.py export-current --output ./exports
```

The command writes:

- `conversation.html` — single-file chat replay page for human collaborators.
- `ai-handoff.md` — markdown package to paste into Gemini, Claude, ChatGPT, or Codex.
- `conversation.md` — readable markdown transcript.
- `conversation.raw.json` — structured archive for later conversion.

## Routing

Decide source by user signal, not by guessing:

1. User says “当前对话”, “这个对话”, “现在这条”, or invokes the skill from a chat → `export-current`. Source auto-detects from environment (`CLAUDE_CODE_SESSION_ID` / `CLAUDECODE` → claude-code; `CODEX_THREAD_ID` → codex).
2. User provides a Codex thread id → `export --thread-id <id>` (auto-resolves to `--source codex`).
3. User provides a Claude Code session UUID → `export --session-id <uuid>` (auto-resolves to `--source claude-code`).
4. User provides a JSONL path → `export --rollout <path> --source codex|claude-code`. If the path is under `~/.codex/sessions/` use `codex`; if under `~/.claude/projects/` use `claude-code`.

If auto-detection cannot decide, ask the user which source.

## Modes

- `--mode share` (default) — strips developer messages, environment context, raw events, and tool outputs. Safe to send to another AI.
- `--mode with-tools` — include tool calls and truncated tool outputs. Use when the user asks for tool/execution detail.
- `--mode raw-archive` — full archive for local debugging. Warn the user that this may contain developer instructions, environment context, and full tool output.

## Commands

Current conversation, auto-detect source:

```bash
python3 /path/to/dialogue-handoff-export/scripts/exporter.py export-current --output ./exports
```

Force a specific source for the current window:

```bash
python3 /path/to/dialogue-handoff-export/scripts/exporter.py export-current --source claude-code --output ./exports
```

Specific Codex thread id:

```bash
python3 /path/to/dialogue-handoff-export/scripts/exporter.py export --thread-id 019e6224-6a78-73f1-b1d4-7757cfc73c39 --output ./exports
```

Specific Claude Code session id:

```bash
python3 /path/to/dialogue-handoff-export/scripts/exporter.py export --session-id a1709565-2d83-475d-af0d-0ee623dbb5e3 --output ./exports
```

Specific rollout file:

```bash
python3 /path/to/dialogue-handoff-export/scripts/exporter.py export --rollout /path/to/rollout.jsonl --source codex --output ./exports
python3 /path/to/dialogue-handoff-export/scripts/exporter.py export --rollout ~/.claude/projects/<slug>/<uuid>.jsonl --source claude-code --output ./exports
```

Include tool summaries:

```bash
python3 /path/to/dialogue-handoff-export/scripts/exporter.py export-current --mode with-tools --output ./exports
```

Local full archive (warn the user):

```bash
python3 /path/to/dialogue-handoff-export/scripts/exporter.py export-current --mode raw-archive --output ./exports
```

## Backward compatibility

The original `scripts/codex_context_exporter.py` is kept as a thin shim. It forwards all arguments to `exporter.py` with `--source codex` injected, so existing skill consumers and any pinned paths keep working without changes.

## Implementation Notes

- Codex: `find_current` reads `CODEX_THREAD_ID`; thread metadata comes from `state_*.sqlite`, then falls back to globbing `sessions/**/*<id>*.jsonl`.
- Claude Code: `find_current` reads `CLAUDE_CODE_SESSION_ID`; sessions are located by scanning `~/.claude/projects/*/`. Metadata (title, cwd, timestamps) is derived from the JSONL itself: `ai-title` events, the first non-reminder user message, and per-event `cwd`.
- Claude Code filters injected harness blocks: messages that are entirely `<system-reminder>...</system-reminder>` are dropped; trailing reminders on real user messages are stripped; slash-command envelopes (`<command-name>`, `<command-message>`, `<local-command-stdout>`) are removed before rendering.
- Tool call pairing in Claude Code: assistant messages emit both `text` and `tool_use` blocks in one event — these are split into separate canonical records. Tool results come back as user messages with `content[].type == "tool_result"` and are paired by `tool_use_id`.
- The default `share` mode excludes developer messages, environment context, raw events, and tool outputs.
- The script is standard-library Python only.
- If `export-current` fails because no session id is in the environment, ask the user for a thread id / session id / rollout file path.
