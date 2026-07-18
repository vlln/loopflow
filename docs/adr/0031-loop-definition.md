---
title: ADR 0031 — loop.md 作为 loop 定义文件
description: 引入 loop.md 作为 loop 的声明式定义文件，frontmatter 给机器读，body 给 Agent 和人类读
type: adr
status: accepted
created: 2026-07-18T00:00:00Z
---

# ADR 0031: loop.md 作为 loop 定义文件

## Context

当前 loop 的元数据分散在 `workflow.py` 的 `meta` 字典中。引入调度机制后，需要新的元数据字段（triggers、resources），这些字段的消费者是 dispatcher 而非 executor。

dispatcher 需要扫描所有 loop 的元数据来做路由决策，但不能 import 每个 loop 的 `workflow.py`——那会引入 Python 执行开销，且一个 loop 的 import 错误会阻塞其他 loop。

## Decision

引入 `loop.md` 作为 loop 的必选定义文件，与 `workflow.py` 同级：

```
~/.loopflow/loops/<name>/
├── loop.md              # 声明式定义（必选）
├── workflow.py          # 编排逻辑
└── agents/              # agent 定义
```

`loop.md` 使用 YAML frontmatter + Markdown body：

- **Frontmatter**：机器可读的结构化元数据（name、description、triggers、resources）
- **Body**：Agent 和人类可读的文档（目的、流程、权限边界、升级条件）

**loop.md 是必选的。** 没有 loop.md 的目录不被视为 loop——`loop list` 不列出，`loop run` 拒绝执行。这是消除双重真相的机制：身份信息（name、description）只在 loop.md 中定义，不在 workflow.py meta 中重复。

### Frontmatter 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | loop 唯一标识 |
| description | string | 是 | 简短描述 |
| triggers | object[] | 否 | 触发声明列表 |
| triggers[].type | string | 是 | manual / cron / watch |
| triggers[].schedule | string | 否 | cron 表达式（type=cron 时必填） |
| triggers[].paths | string[] | 否 | 监视路径（type=watch 时必填） |
| triggers[].pattern | string | 否 | 文件匹配模式（type=watch 时） |
| resources | object[] | 否 | 需要的资源类型 |
| resources[].type | string | 是 | 资源类型名（如 repo） |

**注意：`state` 不在 loop.md 中声明。** loop 层的视角下，workflow.py 是一个可执行的黑盒——它的内部状态（重试计数、阶段标记等）是编排层的实现细节，不属于调度层的声明。`state` 保持在 `workflow.py` 的 `meta.state` 中。

### 示例

```markdown
---
name: fix-issue
description: 接收 issue，triage，修复，review 循环，合并
triggers:
  - type: manual
  - type: cron
    schedule: "*/5 * * * *"
resources:
  - type: repo
---

# fix-issue

## 目的

接收项目 issue，自动 triage → 实现修复 → review 对抗 → CI 验证 → 合并。

## 权限边界

- 可以创建分支、修改代码、运行测试
- 不可以直接 push 到 main
- 3 次 review 不通过 → 升级为人
```

### workflow.py meta 精简

`workflow.py` 的 `meta` 保留 `phases`（展示用），其余字段（name、description、triggers、resources、state）从 `loop.md` 的 frontmatter 读取。discovery 模块改为读取 `loop.md` 而非 import `workflow.py`。

### 一致性

此模式与 loopflow 已有的 agent 定义文件（`agents/*.md`）一致——都是 frontmatter + body 的 Markdown 文件。

## Consequences

### 正面

- Dispatcher 扫描 loop 元数据时只需 parse frontmatter，无需 import Python
- Body 为 Agent 和人类提供文档入口，取代碎片化的"loop 说明"
- 与 agent 定义文件格式一致，降低概念负担
- `workflow.py` 角色更纯粹：编排逻辑，不含元数据声明

### 负面

- 引入新文件类型，loop 目录从 2 个核心文件（workflow.py + agents/）变为 3 个（+ loop.md）
- `workflow.py` 的 `meta` 和 `loop.md` 的 frontmatter 有字段重叠，需要明确规则：loop.md 是权威源，workflow.py 的 meta 只保留 phases

### 迁移

- 现有 loop 需要补一个 `loop.md`（至少含 name 和 description）才能继续被 `loop list` 发现和 `loop run` 执行
- `make-loop` skill 更新为生成 `loop.md`

## 验证

本 ADR 不需要验证——它是格式约定，不涉及技术选型。