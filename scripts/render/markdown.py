"""Minimal markdown -> HTML renderer (sufficient for chat content)."""

from __future__ import annotations

import html
import re


def inline_markdown(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


def render_prose_html(text: str) -> str:
    lines = text.strip("\n").splitlines()
    blocks: list[str] = []
    list_items: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            blocks.append("<p>" + "<br>".join(inline_markdown(line) for line in paragraph) + "</p>")
            paragraph.clear()

    def flush_list() -> None:
        if list_items:
            blocks.append("<ul>" + "".join(f"<li>{item}</li>" for item in list_items) + "</ul>")
            list_items.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            flush_list()
            continue
        heading = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        bullet = re.match(r"^[-*]\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            flush_list()
            level = min(len(heading.group(1)) + 2, 6)
            blocks.append(f"<h{level}>{inline_markdown(heading.group(2))}</h{level}>")
        elif bullet:
            flush_paragraph()
            list_items.append(inline_markdown(bullet.group(1)))
        else:
            flush_list()
            paragraph.append(line)
    flush_paragraph()
    flush_list()
    return "\n".join(blocks)


def render_markdown_html(text: str) -> str:
    parts = re.split(r"```([A-Za-z0-9_-]*)\n(.*?)```", text, flags=re.S)
    rendered: list[str] = []
    for index in range(0, len(parts), 3):
        prose = parts[index]
        if prose:
            rendered.append(render_prose_html(prose))
        if index + 2 < len(parts):
            lang = parts[index + 1].strip()
            code = parts[index + 2]
            class_attr = f' class="language-{html.escape(lang)}"' if lang else ""
            rendered.append(f"<pre><code{class_attr}>{html.escape(code.rstrip())}</code></pre>")
    return "\n".join(part for part in rendered if part)
