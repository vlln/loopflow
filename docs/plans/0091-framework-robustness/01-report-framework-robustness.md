---
title: 框架健壮性修复 Report
description: BL-017/018/019 三处框架层 bug 修复完成，三后端实测端到端跑通 deep-research，unit 364 passed
type: report
status: complete
created: 2026-07-26T09:30:00Z
---

# Summary

按 ADR-0051 / BL-017~019 完成三处框架层定点修复：`render_template` 模板变量 str 化、`parse_agent` body 排除 frontmatter、pi 后端改用 `text_end` 消息级事件。三后端（kimi/pi/pi-acp）实测端到端跑通 deep-research（各 24 claim），unit 364 passed 零回归。uv.lock 同步至 0.22.0。

# Changes

| BL | 文件 | 改动 | commit |
|----|------|------|--------|
| BL-017 | `src/loopflow/domain/agent_def.py` | `_replace` 返回 `"" if value is None else str(value)`，防 integer/None 模板变量触发 `re.sub` TypeError | 1ad12d4 |
| BL-018 | `src/loopflow/infrastructure/repository.py` | `body = parts[2].strip()`，body 只含 markdown 正文不含 frontmatter；避免 prompt 以 `---` 开头被 pi 误解析为未知选项（ADR-0051） | 1ad12d4 |
| BL-019 | `src/loopflow/infrastructure/backends/pi.py` | `_parse_line` 改判 `text_end` 事件返回 `event.get("content", "")`，弃 `text_delta` token 片段；修复 `_extract_text` 的 `"\n".join` 在 JSON 字符串值内插入裸 `\n` 破坏流式 JSON | 1ad12d4 |
| chore | `uv.lock` | loopflow 版本 0.21.0 → 0.22.0 | e7dda0c |

# 改动细节

## BL-017 render_template str 化

`render_template` 用 `re.sub(r"\{\{\s*(\w+)\s*\}\}", _replace, body)` 替换模板占位符。原 `_replace` 直接 `return kwargs[name]`，当模板变量为 integer 或 None 时，`re.sub` 的 repl 函数要求返回 str，抛 `TypeError: expected string or bytes-like object`。改为 `value = kwargs[name]; return "" if value is None else str(value)` —— None 归一为空串（模板语义"缺省"），其他类型 str 化。

## BL-018 parse_agent body 切分

`parse_agent` 用 `parts = content.split("---")` 切分 markdown agent 文件。原 `body = content.strip()` 把 frontmatter（`---\n...yaml...\n---`）也并入 body，导致 prompt 以 `---` 开头。pi 这类把 prompt 作为位置 argv 传给子进程的 CLI 后端，会把 `---` 误解析为未知选项。改为 `body = parts[2].strip()` —— `parts[0]` 为空、`parts[1]` 为 frontmatter yaml、`parts[2]` 为正文。frontmatter 是元数据不是 prompt 内容。

## BL-019 pi text_end

pi 后端 `_parse_line` 解析 pi stdout 的 SSE 事件。原监听 `assistantMessageEvent.type == "text_delta"` 返回 `event.delta`（token 级片段）。`_extract_text` 用 `"\n".join(chunks)` 拼接片段 —— 当片段是流式 JSON 的子串时，join 会在 JSON 字符串值内插入裸 `\n`，破坏 JSON 解析。改为监听 `text_end`（消息级完整块）返回 `event.content` —— 一次拿完整文本块，不再走 token 拼接。

# Verification Results

| 验证 | 结果 |
|------|------|
| `pytest tests/unit -q` | 364 passed |
| kimi 后端实测 deep-research | 4 phase 全走通，24 claim 通过，report.md 产出 |
| pi 后端实测 deep-research | 修 text_end 后跑通，24 claim |
| pi-acp 后端实测 deep-research | ACP 模式跑通，24 claim |
| 分支隔离 `git diff develop..fix/0091-framework-robustness --stat` | 只含 agent_def/repository/pi/uv.lock（4 files, +13 -5） |

# Notes

- **uv.lock 同步**：0.22.0 迭代发版后 uv.lock 仍记 0.21.0，本分支补同步。属 chore，单独 commit（e7dda0c）与 fix（1ad12d4）拆分。
- **work_dir 传递链**：本分支不含 context.py/runtime.py/execution.py/cli.py 的 work_dir 删除 —— 这些"先加又删"的改动最终回到原状，diff 无泄漏。work_dir 的 CLI 侧新增见 [0092](../0092-work-dir/README.md)。
- **三后端实测证据与 0092 共用**：本轮三后端实测端到端 deep-research 同时验证了 0091 的框架修复与 0092 的 `--work-dir`（loop 在 chdir 后的 cwd 下跑通）。
- **不合并分支**：由用户合并，本容器只交付代码 + 文档。
