# dialogue-handoff-export

把单条 AI 对话导出成"可分享 / 可接力"的交接包。当前支持 **Codex** 和 **Claude Code** 两种来源。

每次导出会落 4 个文件到 `exports/<日期>_<来源>_<标题>_<id>_<mode>/`:

- `conversation.html` — 单文件聊天回放页(给人看)
- `ai-handoff.md` — 给另一个 AI 粘贴接着聊用的 markdown
- `conversation.md` — 纯文本通读
- `conversation.raw.json` — 结构化原档

## 安装

把整个仓库克隆到 Codex 的 skill 目录:

```bash
git clone https://github.com/chuspeeism/dialogue-handoff-export.git ~/.codex/skills/dialogue-handoff-export
```

也可以放任意位置,直接调用 `scripts/exporter.py`。脚本只用标准库,无需 pip install。

## 使用

### 导出当前对话(自动识别)

```bash
python3 ~/.codex/skills/dialogue-handoff-export/scripts/exporter.py export-current --output ./exports
```

在 Codex 里读 `CODEX_THREAD_ID`,在 Claude Code 里读 `CLAUDE_CODE_SESSION_ID`。

### 通过会话 id 导出

```bash
# Codex thread id
python3 .../scripts/exporter.py export --thread-id <uuid> --output ./exports

# Claude Code session id
python3 .../scripts/exporter.py export --session-id <uuid> --output ./exports
```

### 通过原始 JSONL 文件导出

```bash
python3 .../scripts/exporter.py export --rollout /path/to/rollout.jsonl --source codex
python3 .../scripts/exporter.py export --rollout ~/.claude/projects/<slug>/<uuid>.jsonl --source claude-code
```

### 导出模式

- `--mode share`(默认):剥掉 developer 消息、环境上下文、原始事件、工具输出,适合分享给别人或别的 AI
- `--mode with-tools`:包含工具调用和截断后的工具输出,用于讨论执行细节
- `--mode raw-archive`:本地完整归档,会带 developer instructions 和完整工具输出,慎用

## 架构

```
scripts/
├── exporter.py                  统一入口
├── codex_context_exporter.py    向后兼容 shim,转发到 exporter.py --source codex
├── render/                      渲染层(HTML / markdown / handoff 模板)
│   ├── conversation.py
│   ├── html.py
│   └── markdown.py
└── sources/                     数据源插件
    ├── base.py                  Source 接口 + canonical event schema
    ├── codex.py                 ~/.codex/state_*.sqlite + sessions/*.jsonl
    └── claude_code.py           ~/.claude/projects/<slug>/<uuid>.jsonl
```

### 数据源对比

| 维度 | Codex | Claude Code |
|---|---|---|
| 当前会话 env | `CODEX_THREAD_ID` | `CLAUDE_CODE_SESSION_ID` |
| 索引 | `~/.codex/state_*.sqlite` | 无中心 DB,扫 `~/.claude/projects/*` |
| 事件结构 | `response_item` 套 message / function_call / function_call_output | 顶层 `user` / `assistant`,assistant 的 `message.content` 内嵌 `text` 与 `tool_use` 块,工具结果以 `user` 消息回传 |
| 标题 | `threads.title` | `ai-title` 事件的 `aiTitle` |

### 加新数据源

在 `sources/` 加一个文件实现 `Source` 接口(`find_current` / `find_by_id` / `find_by_rollout` / `iter_canonical_events`),在 `sources/__init__.py` 注册一行,完事。渲染层不用动。

## 向后兼容

仓库前身是只支持 Codex 的 `codex_context_exporter.py`。该文件保留为 23 行 shim,自动注入 `--source codex` 后转发,旧调用不受影响。

## 相关

- HTML 顶部"复制接力包"按钮把 `ai-handoff.md` 内容写入剪贴板,可直接粘贴到下一个 AI;"复制会话 ID"用于二次导出。注意 `file://` 模式下部分浏览器禁止写剪贴板,如不响应请用 `python3 -m http.server` 起本地服务再访问。
