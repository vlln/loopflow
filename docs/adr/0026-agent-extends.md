---
title: ADR 0026 — Agent extends 继承机制
description: 通过 extends 字段实现 agent 之间的 prompt 继承，替代 shared.md/protocol.md 公共文件方案
type: adr
status: accepted
created: 2026-07-12T00:00:00Z
---

# ADR 0026: Agent extends 继承机制

## Context

多个 agent 共享公共 prompt（如工作约定、输出规范），当前方案是 `protocol.md` 由 workflow 手动加载注入。这破坏了 prompt 组装的统一性——workflow 不应关心 prompt 内容。

## Decision

引入 `extends` 字段，允许 agent 继承另一个 agent 的 body 和 frontmatter。

### 格式

```yaml
# agents/_base.md（抽象 agent，_ 前缀约定不直接调用）
---
name: _base
description: 公共工作约定
---
## 工作约定
- 产出语言：{{ language }}
```

```yaml
# agents/reader.md
---
name: reader
extends: _base
skills:
  - paperutils
---
# Phase 1: Reader
...
```

### 合并规则

| 字段类型 | 规则 |
|---------|------|
| body | 拼接（父在前） |
| list（skills、env、mcpServers） | 合并（父 + 子） |
| scalar（model、isolation） | 子覆盖父 |
| input/output | 子覆盖父 |
| name/description | 子不变 |

### 拼装顺序

```
_base body → child body → skills → task
  ← 不易变                    易变 →
```

### 抽象 agent 约定

`_` 前缀的 agent 文件不通过 `list_agents()` 列出。

## Consequences

- `protocol.md` 不再需要，workflow 的 `prompt()` 包装器删除
- `_base.md` 支持 `{{ param }}` 模板渲染，比 `protocol.md` 更强大
- 三层 prompt 模型：body（含 extends）→ skills → task

## Alternatives Considered

- **shared.md**：新文件类型，需要单独的 loader 和规则，不支持 `{{ }}` 模板
- **workflow 手动注入**：当前方案，破坏职责分离

## References

- [[0025-agent-frontmatter-alignment]] — agent frontmatter 格式对齐