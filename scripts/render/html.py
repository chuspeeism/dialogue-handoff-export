"""Single-file HTML renderer for the conversation replay page."""

from __future__ import annotations

import html
import json
from typing import Any

from .markdown import render_markdown_html


def _script_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def _message_heading(role: str) -> str:
    return "User" if role == "user" else "Assistant"


def render_html(data: dict[str, Any], handoff_md: str) -> str:
    thread = data["thread"]
    source_label = data.get("source_label", data.get("source", ""))
    title = thread.get("title") or f"{source_label} Conversation"
    handoff_json = _script_json(handoff_md)
    data_json = _script_json(data)

    bubbles: list[str] = []
    for message in data["messages"]:
        role = message["role"]
        phase = message.get("phase") or ""
        role_label = _message_heading(role)
        phase_html = f'<span class="phase">{html.escape(phase)}</span>' if phase else ""
        content = render_markdown_html(message.get("content", ""))
        bubbles.append(
            f"""
            <article class="message {html.escape(role)}">
              <div class="meta">
                <span>{role_label}</span>
                {phase_html}
              </div>
              <div class="bubble">{content}</div>
            </article>
            """
        )

    tool_section = ""
    if data["tool_events"]:
        tool_items = []
        for event in data["tool_events"]:
            title_text = f"{event.get('kind')} · {event.get('name')}"
            if event["kind"] == "function_call":
                body = json.dumps(event.get("arguments"), ensure_ascii=False, indent=2)
                lang = "json"
            else:
                body = str(event.get("output", ""))
                lang = "text"
            tool_items.append(
                f"""
                <details>
                  <summary>{html.escape(title_text)}</summary>
                  <pre><code class="language-{lang}">{html.escape(body)}</code></pre>
                </details>
                """
            )
        tool_section = f'<section class="tools"><h2>工具调用摘要</h2>{"".join(tool_items)}</section>'

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} · 对话交接器</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #20242a;
      --muted: #667085;
      --line: #d9dee7;
      --user: #105c52;
      --user-bg: #dff3ed;
      --assistant: #243b63;
      --assistant-bg: #ffffff;
      --accent: #c65f28;
      --code-bg: #111827;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 5;
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.94);
      backdrop-filter: blur(12px);
    }}
    .topbar {{
      max-width: 1040px;
      margin: 0 auto;
      padding: 16px 20px;
      display: flex;
      gap: 16px;
      align-items: center;
      justify-content: space-between;
    }}
    h1 {{
      margin: 0;
      font-size: 20px;
      font-weight: 700;
      letter-spacing: 0;
    }}
    .submeta {{
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
    }}
    .actions {{
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    button {{
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      color: var(--text);
      padding: 0 12px;
      font: inherit;
      cursor: pointer;
    }}
    button.primary {{
      border-color: var(--accent);
      background: var(--accent);
      color: white;
    }}
    main {{
      max-width: 1040px;
      margin: 0 auto;
      padding: 24px 20px 48px;
    }}
    .message {{
      display: grid;
      gap: 7px;
      margin: 18px 0;
    }}
    .message.user {{
      justify-items: end;
    }}
    .message.assistant {{
      justify-items: start;
    }}
    .meta {{
      color: var(--muted);
      font-size: 12px;
      display: flex;
      gap: 8px;
      align-items: center;
    }}
    .phase {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 1px 7px;
      background: var(--panel);
    }}
    .bubble {{
      width: min(820px, 100%);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px 18px;
      overflow-wrap: anywhere;
      box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }}
    .user .bubble {{
      background: var(--user-bg);
      border-color: #b7d9cf;
    }}
    .assistant .bubble {{
      background: var(--assistant-bg);
    }}
    p {{
      margin: 0 0 12px;
    }}
    p:last-child {{
      margin-bottom: 0;
    }}
    h3, h4, h5, h6 {{
      margin: 18px 0 8px;
      line-height: 1.3;
    }}
    ul {{
      margin: 8px 0 12px;
      padding-left: 22px;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      font-size: 0.93em;
    }}
    p code, li code {{
      background: #eef1f5;
      border: 1px solid #dce2ea;
      border-radius: 5px;
      padding: 1px 5px;
    }}
    pre {{
      margin: 12px 0;
      padding: 14px;
      overflow-x: auto;
      border-radius: 8px;
      background: var(--code-bg);
      color: #e5e7eb;
      white-space: pre;
    }}
    pre code {{
      color: inherit;
      background: transparent;
      border: 0;
      padding: 0;
    }}
    .tools {{
      margin-top: 32px;
      border-top: 1px solid var(--line);
      padding-top: 18px;
    }}
    .tools h2 {{
      font-size: 16px;
      margin: 0 0 12px;
    }}
    details {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px 12px;
      margin: 8px 0;
    }}
    summary {{
      cursor: pointer;
      color: var(--assistant);
      font-weight: 600;
    }}
    @media (max-width: 720px) {{
      .topbar {{
        display: block;
      }}
      .actions {{
        margin-top: 12px;
        justify-content: flex-start;
      }}
      .bubble {{
        width: 100%;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="topbar">
      <div>
        <h1>{html.escape(title)}</h1>
        <div class="submeta">{html.escape(source_label)} · {html.escape(data.get("mode", ""))} · {html.escape(data.get("exported_at", ""))} · {html.escape(thread.get("id", ""))}</div>
      </div>
      <div class="actions">
        <button type="button" id="copy-handoff" class="primary">复制接力包</button>
        <button type="button" id="copy-thread">复制会话 ID</button>
      </div>
    </div>
  </header>
  <main>
    {"".join(bubbles)}
    {tool_section}
  </main>
  <script type="application/json" id="conversation-data">{data_json}</script>
  <script>
    const handoff = {handoff_json};
    const threadId = {_script_json(thread.get("id", ""))};
    const copy = async (text) => {{
      await navigator.clipboard.writeText(text);
    }};
    document.getElementById("copy-handoff").addEventListener("click", async () => {{
      await copy(handoff);
    }});
    document.getElementById("copy-thread").addEventListener("click", async () => {{
      await copy(threadId);
    }});
  </script>
</body>
</html>
"""
