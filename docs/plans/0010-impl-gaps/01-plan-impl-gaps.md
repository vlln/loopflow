---
title: 01-plan-impl-gaps
description: 实现 A1-A4：meta.phases 声明、agent 事件 phase 归属、agent_def 接入、模板渲染
type: plan
status: done
created: 2026-07-08T12:00:00Z
---

# 01-plan-impl-gaps: 实现补全 A1-A4

## Context

ADR 0010 明确了 loopflow 设计边界，并识别出 4 项已有设计但未实现的补全：

| # | 能力 | 已有设计 | 缺的实现 |
|---|------|---------|---------|
| A1 | `meta` 声明 `phases` | `meta` dict + `_load_meta()` | 加 `phases` 字段验证 |
| A2 | Agent 事件携带 `phase` 归属 | events.jsonl 格式 | agent 事件加 `phase` 字段 |
| A3 | `agent()` 接受 `agent_def` 参数 | `AgentDef` + `parse_agent()` | `agent()` 接入 agent 定义加载 |
| A4 | Agent body 模板渲染 `{{param}}` | Spec 已定义占位符语法 | 模板渲染引擎 |

## Request

### A1: meta.phases 声明

`workflow.py` 的 `meta` dict 支持可选的 `phases` 字段：

```python
meta = {
    "name": "my-loop",
    "description": "...",
    "phases": [
        {"title": "Research", "detail": "收集信息"},
        {"title": "Translate", "detail": "翻译结果"},
    ],
}
```

- `discovery._load_meta()` 验证 `phases` 格式（list of dict，每个含 `title`）
- CLI 层将 `meta` 传递给 RunContext
- `_emit_phase()` 检查 phase 是否在声明列表中（偏差时 log warning）

### A2: Agent 事件携带 phase 归属

- `RunContext` 新增 `_current_phase: str | None`
- `_emit_phase()` 设置 `_current_phase`
- `agent()` 在写入缓存事件时，`agent_start` 携带 `phase` 字段

### A3: agent() 接受 agent_def 参数

- `agent()` 新增 `agent_def: str | None` 参数
- 默认值 `"default"`，查找 `{loop_dir}/agents/{agent_def}.md`
- 加载 `AgentDef`，将 body 作为系统提示词，与 prompt 合并
- 合并模式：`{body}\n\n---\n\nTask: {prompt}`
- `**kwargs` 传递给模板渲染

### A4: Agent body 模板渲染

- `{{param}}` → kwargs 中的值
- 简单字符串替换，不引入模板引擎依赖
- 缺少参数时报错

## Output Format

| 文件 | 变更 |
|------|------|
| `src/loopflow/runtime.py` | RunContext 加 `_current_phase`、`loop_dir`；agent() 加 `agent_def`、`**kwargs`；_emit_phase() 设 current_phase |
| `src/loopflow/discovery.py` | `load_loop()` 返回 loop_dir；`_load_meta()` 验证 `phases` |
| `src/loopflow/agent.py` | 新增 `render_template(body, **kwargs)` 函数 |
| `src/loopflow/cli.py` | 将 meta 传入 RunContext |
| `tests/unit/test_runtime.py` | A2（phase 归属）、A3（agent_def 加载）、A4（模板渲染） |
| `tests/unit/test_discovery.py` | A1（meta.phases 验证） |
| `tests/unit/test_agent.py` | A4（模板渲染函数） |

## Constraints

- 不与现有 API 签名冲突：`agent_def` 和 `**kwargs` 为新增可选参数
- 模板渲染不引入第三方依赖（Python 标准库 `string.Template` 或简单 `str.replace`）
- `agent_def` 默认值为 `"default"`，如果 agents/default.md 不存在则退化为纯 prompt 模式
- meta.phases 为可选字段，不声明时行为不变
- 向后兼容：所有现有 loop 和测试不受影响

## Checkpoint

1. `meta.phases` 声明正确验证，格式错误时报错
2. agent 缓存事件中 `agent_start` 携带 `phase` 字段
3. `agent("指令", agent_def="reader")` 正确加载 agents/reader.md 并合并 body
4. `{{param}}` 模板变量正确替换
5. 现有 83 个测试全部通过
6. 新增测试覆盖 N/B/E/F 四场景

## Steps

1. A4: 实现 `render_template()` 模板渲染函数 + 单元测试
2. A2: RunContext 加 `_current_phase`，agent 事件加 `phase` 字段 + 单元测试
3. A1: `_load_meta()` 验证 `phases` 字段 + 单元测试
4. A3: `agent()` 加 `agent_def` 参数，加载 agent 定义 + 集成测试
5. CLI: 传递 meta 到 RunContext
6. 全量回归测试，确保向后兼容