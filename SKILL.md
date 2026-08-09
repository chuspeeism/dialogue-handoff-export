---
name: dialogue-handoff-export
description: Export a single explicitly targeted AI conversation (Codex or Claude Code) as a dialogue handoff package. Use when the user asks to use 对话交接器, export/share the current conversation, 导出当前对话, 导出聊天记录, create an AI handoff markdown, produce a ChatGPT-like conversation replay HTML, or export by thread id / session id / JSONL file path. Do not use for listing recent conversations or searching chat history.
---

# Dialogue Handoff Export

Export exactly one conversation that the user explicitly targets. Do not list recent conversations, search historical conversations, or batch-export a project.

This skill is a thin caller. The export engine lives in **context-hub** (`hub/cli.py`), which shares its connectors, handoff format, and secret scanner with the Context Hub app. There is no separate implementation here to maintain.

## Step 1 — locate context-hub

```bash
HUB="${CONTEXT_HUB_HOME:-$(cat ~/.context-hub/home 2>/dev/null)}"
[ -d "$HUB" ] && echo "$HUB" || echo "NOT FOUND"
```

`~/.context-hub/home` is rewritten every time the Hub launches, so it tracks the folder even if it moves. If it prints `NOT FOUND`, tell the user context-hub is not installed or has never been launched, and ask for its path — do not guess and do not reimplement the exporter.

## Step 2 — export

Run from the user's current workspace so `exports/` lands near their work.

Current conversation (auto-detects Codex vs Claude Code from `CODEX_THREAD_ID` / `CLAUDE_CODE_SESSION_ID`):

```bash
(cd "$HUB" && python3 -m hub.cli export-current --output "$OLDPWD/exports")
```

A specific conversation:

```bash
(cd "$HUB" && python3 -m hub.cli export --session-id <uuid> --output "$OLDPWD/exports")   # Claude Code
(cd "$HUB" && python3 -m hub.cli export --thread-id <uuid> --output "$OLDPWD/exports")    # Codex
(cd "$HUB" && python3 -m hub.cli export --conv-id <id> --output "$OLDPWD/exports")        # any local source
(cd "$HUB" && python3 -m hub.cli export --file <path.jsonl> --source codex --output "$OLDPWD/exports")
```

The CLI reads the source files directly — the Hub server does not need to be running.

## Output

One folder per export, `exports/<date>_<source>_<title>_<id8>_<mode>/`:

- `conversation.html` — single-file replay for people; images inlined as data URIs, so it survives being emailed
- `ai-handoff.md` — paste into the next AI
- `conversation.md` — plain transcript
- `conversation.raw.json` — structured archive

## Modes

| `--mode` | Contents |
|---|---|
| `share` (default) | Prose only — no tool calls, no thinking. Safe to hand to a collaborator. |
| `with-tools` | Adds tool calls and thinking as fold-outs. For discussing execution detail. |
| `raw-archive` | `with-tools` plus image payloads in the JSON and a copy of the original JSONL. Local archive; may contain harness instructions and full tool output. |

## Options worth knowing

- `--target chatgpt|claude|gemini|豆包|千问|deepseek|kimi|元宝` — compress the handoff package to that platform's single-paste budget (early turns fold to summaries, recent turns stay verbatim). `--full` disables it.
- `--no-redact` — skip the secret scan. It is **on by default**: API keys, tokens, private keys, and connection strings in the handoff package are masked before writing.
- `python3 -m hub.cli list --source claude-code --limit 10` — find a conversation id. Use only when the user hands you an ambiguous target; this skill does not browse history on its own.

## Routing

- User wants **one conversation exported to files** → this skill.
- User wants to **browse, search, or combine several conversations** → that is the Context Hub app (`python3 app.py` in `$HUB`, then `http://localhost:8765`), not this skill.
