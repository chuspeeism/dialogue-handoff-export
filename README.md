# dialogue-handoff-export

把单条 AI 对话导出成「可分享 / 可接力」的交接包。支持 **Codex**、**Claude Code**、**OpenClaw**、**Hermes** 四个本地来源。

## 这个仓库现在只剩一张说明书

导出引擎已合入 **context-hub**（`hub/cli.py`）。原因是两边内核本来就同源：本仓库的 `scripts/sources/` 与 context-hub 的 `hub/connectors/` 解决同一个问题，但各自演化后差异超过 87%，等于维护两套。合并后：

- **内核归 context-hub**：它支持 4 个本地源（本仓库原先只有 2 个）、图片提取、接力包 token 预算压缩、敏感信息扫描
- **本仓库归 skill 契约**：`SKILL.md` 描述何时触发、怎么调用，不再有第二份实现

反过来，本仓库原先独有、context-hub 缺失的两块能力也已经补进产品：**单文件 HTML 回放页**（图片内嵌成 data URI，能直接寄出去）和 **share / with-tools / raw-archive 三档模式**。

产品与 skill 解决的不是同一个问题，所以形态没有合并：context-hub 的 Web UI 服务「人在浏览器里翻对话库」，本 skill 服务「正在会话里干活的 AI agent」——它没有浏览器，只知道当前这条对话，要的是落到磁盘的文件。CLI 就是产品为后者长出的第二个前端。

## 安装

```bash
git clone https://github.com/chuspeeism/dialogue-handoff-export.git ~/.codex/skills/dialogue-handoff-export
```

前置依赖：本机装有 context-hub 并至少启动过一次（启动时会把自身路径写到 `~/.context-hub/home`，skill 据此定位）。也可以自己设 `CONTEXT_HUB_HOME`。

## 使用

```bash
HUB="${CONTEXT_HUB_HOME:-$(cat ~/.context-hub/home)}"

# 当前对话（自动识别 Codex / Claude Code）
(cd "$HUB" && python3 -m hub.cli export-current --output "$OLDPWD/exports")

# 指定会话
(cd "$HUB" && python3 -m hub.cli export --session-id <uuid> --output "$OLDPWD/exports")
(cd "$HUB" && python3 -m hub.cli export --thread-id <uuid> --output "$OLDPWD/exports")
```

不需要启动 Hub 服务，CLI 直接读源文件。完整参数见 `SKILL.md` 或 `python3 -m hub.cli export --help`。

## 输出

`exports/<日期>_<来源>_<标题>_<id前8位>_<模式>/`

- `conversation.html` — 单文件聊天回放页（给人看，图片内嵌）
- `ai-handoff.md` — 给另一个 AI 粘贴接着聊
- `conversation.md` — 纯文本通读
- `conversation.raw.json` — 结构化原档
