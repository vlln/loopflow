---
title: ADR 0051 — Agent body 剥离 frontmatter
description: parse_agent 的 body 从"整文件内容"变为"frontmatter 之后的 markdown 正文"，避免 system prompt 含元数据、CLI backend 误把 --- 当 unknown option
type: adr
status: accepted
created: 2026-07-26T00:00:00Z
---

# ADR 0051: Agent body 剥离 frontmatter

## Context

`parse_agent`（`infrastructure/repository.py`）将 agent `.md` 文件解析为 `AgentDef`，其中 `body` 字段作为 agent 的 system prompt 传递给后端。

修复前 `body = content.strip()`——即整文件内容（含 frontmatter 的 `---` 分隔符及 `name`/`description`/`input`/`output` 等元数据字段）都成为 prompt。这导致两个问题：

1. **system prompt 含 frontmatter 元数据**：`name`、`description`、`input`（JSON Schema）、`output` 等 frontmatter 字段本是为 loopflow 编排层消费的元数据，不应进入 LLM 的 system prompt。prompt 以 `---\nname: planner\n...` 开头而非 markdown 正文。
2. **CLI backend 把 `---` 当 unknown option**：pi 等 CLI backend 把 system prompt 作为 positional argv 传递给子进程；prompt 以 `---` 开头时，getopt 风格的参数解析器把 `---` 误认为未知选项，导致 run 启动即失败。

## Decision

### 1. body = parts[2].strip()

`parse_agent` 用 `content.split("---", 2)` 将文件分为三段：前导空白、frontmatter 文本、正文。`body` 取 `parts[2].strip()`——仅 frontmatter 之后的 markdown 正文，不含 `---` 分隔符和元数据字段。

```python
parts = content.split("---", 2)
if len(parts) < 3:
    raise ValueError(f"No YAML frontmatter found in {file_path}")
frontmatter_text = parts[1].strip()
body = parts[2].strip()  # 仅 markdown 正文
```

body 语义从"整文件"变为"仅正文"。

### 2. 与 ADR-0026 extends 继承一致

ADR-0026 定义的 body 拼接规则（父 body → 子 body → skills → task）拼接的本来就是正文内容。剥离 frontmatter 后，extends 继承链拼接的 body 全部为正文，语义与 ADR-0026 的设计意图完全对齐。

### 3. 在 parse_agent 层剥离（单一职责）

在 `parse_agent`（文件 I/O / 解析层）剥离 frontmatter，而非在 runner 或 marshalling 层。parse_agent 是所有下游消费 body 的唯一入口——在此层剥离，runner、marshalling、extends 合并等所有下游代码自然受益，无需各自处理。

## Alternatives

| 方案 | 评估 |
|------|------|
| **runner / marshalling 层剥离** | 不采纳。body 在多处被消费（extends 合并、skills 注入、prompt 组装），在消费层剥离需逐个处理且易遗漏；parse_agent 是唯一入口，在此剥离是单一职责 |
| **在 frontmatter 中增加 `strip_frontmatter: true` 开关** | 不采纳。frontmatter 本是元数据、不应进 prompt 是确定性的，不需要可配置 |

## Consequences

- **行为变化**：所有 agent 的 system prompt 不再以 frontmatter 元数据开头，而是以 markdown 正文开头。frontmatter 字段（name/description/input/output 等）仅用于编排层消费，不进入 LLM prompt。
- CLI backend（pi 等）不再把 `---` 当 unknown option，prompt 作 argv 传递时正常执行。
- ADR-0025（frontmatter 格式对齐）和 ADR-0026（extends 继承）中的 body 语义说明需更新：body 指"frontmatter 之后的 markdown 正文"，不含 frontmatter。本 ADR 以引注方式更新，不原地改 ADR-0025/0026。
- 旧 agent 文件无需迁移——frontmatter 本就存在，剥离逻辑在解析层透明完成。

## Verification

已实测验证。用 kimi/pi/pi-acp 三后端端到端跑通 deep-research loop（loop-library/loops/deep-research），agent body 不含 frontmatter 后 planner/researcher/verifier/synthesizer 全部跑通。

复现命令：

```
loop run deep-research --args '{"query":"What is RISC-V"}' --backend kimi
```

结论：可行。三后端均正常完成 run，agent system prompt 以 markdown 正文开头，无 frontmatter 元数据泄露，CLI backend 不再误把 `---` 当 unknown option。

## References

- [ADR-0025](0025-agent-frontmatter-alignment.md) — agent frontmatter 格式对齐 Claude Code
- [ADR-0026](0026-agent-extends.md) — agent extends 继承机制，body 拼接规则
- BL-018 — parse_agent 剥离 frontmatter（本 ADR 对应 backlog 条目）
