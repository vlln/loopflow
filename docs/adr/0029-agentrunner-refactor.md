---
title: ADR 0029 — AgentRunner 重构
description: 将 Agent 从 marshalling 工具重构为 AgentRunner 执行实例，消除 backend 双重创建和两条执行路径的重复
type: adr
status: accepted
created: 2026-07-14T00:00:00Z
---

# ADR 0029: AgentRunner 重构

## Context

ADR 0028 引入了 `Agent` 类作为 "Backend + Capabilities" 的抽象。但实际实现中存在四个问题：

1. **Agent 类贫血。** `Agent` 只做 prompt 组装（`marshal()`、`build_goal_steering()`、`add_goal_to_schema()`），没有执行生命周期。类名暗示它是一个有状态的实体，但实际是三个函数的命名空间。

2. **Backend 实例创建两次。** `runtime.agent()` 中先创建 `backend_instance` 仅为查询 `supports_native_goal`，然后 `_run_subagent()` 内部再创建另一个实例。第一次创建有 Transport 初始化的实际开销。

3. **两条执行路径重复。** `agent()` 正常路径和 `_call_agent_once()` goal loop 路径有几乎相同的 mock/backend-call/JSON-parse/cache 逻辑，违反 DRY。

4. **能力查询需要实例。** `Agent.marshal(backend=backend_instance)` 接收一个完整 Backend 实例，但只查询 `getattr(backend, 'supports_native_goal', False)` —— 这是 class-level 属性，不需要实例。

DDD 分析表明：

- `AgentDef` 是聚合根（纯声明，用户定义的配置）
- `agent()` 函数是用户可见的唯一入口（Agent 实例）
- `Agent` 类不是领域概念——它是实现构件

## Decision

### 1. Agent 类 → AgentRunner 类

```python
# agent.py — 领域层: 纯声明
@dataclass
class AgentDef:
    """聚合根，用户定义的 agent 配置"""
    ...

# runner.py — 应用层: 执行实例
class AgentRunner:
    """Agent 执行实例。持有 AgentDef、Backend、RunContext。"""
    def __init__(self, definition, backend, context):
        self.definition = definition
        self.backend = backend      # 创建一次，不重复
        self.context = context      # RunContext
    
    def run(self, prompt, goal=None, **params) -> Any:
        """完整生命周期: marshal → execute → parse → return"""
        ...
```

### 2. Marshalling 规则 → 模块级函数

```python
# agent.py — 领域服务: 纯函数, 独立可测试
def marshal(ad, prompt, goal, backend, **params) -> tuple[str, dict | None, bool]:
    """尽力而为规则: 将 Agent 能力映射到 Backend 执行"""
    ...

def build_goal_steering(goal, iteration, max_iterations) -> str:
    ...

def add_goal_to_schema(schema) -> dict:
    ...
```

### 3. `agent()` 函数 → 薄 facade

```python
# runtime.py — 面向用户
def agent(prompt, *, agent_def=None, backend=None, goal=None, **kwargs):
    ad = parse_agent(...) if agent_def else None
    be = _make_backend(backend)
    try:
        return AgentRunner(ad, be, _ctx).run(prompt, goal=goal, **kwargs)
    finally:
        be.close()
```

### 4. 统一执行路径

`AgentRunner._execute_once()` 统一 mock/backend-call/JSON-parse/cache 逻辑，正常路径和 goal loop 都走它。

### 影响范围

| 文件 | 变更 |
|------|------|
| `agent.py` | 删除 `Agent` 类，保留 `AgentDef` + 新增模块级函数 `marshal()`, `build_goal_steering()`, `add_goal_to_schema()`, `run_goal_loop()` |
| `runner.py` (新) | 新增 `AgentRunner` 类：`run()`, `_execute_once()`, `_run_goal_loop()` |
| `runtime.py` | `agent()` 简化为薄 facade；移除 `_call_agent_once()`；移除重复的执行逻辑 |
| `tests/unit/test_agent.py` | 更新测试：`Agent` → `AgentRunner` + 模块级函数 |

## Consequences

### 正面

- `Agent` 类不再存在——消除了命名与语义的错位
- `AgentRunner` 有明确的生命周期：创建 → run → close
- Backend 只创建一次，由 `AgentRunner` 持有
- 执行路径统一，消除 DRY 违规
- `agent()` 函数保持用户可见的 API 不变
- Marshalling 函数可独立测试（不需要 Backend 实例）

### 负面

- 新增一个文件 `runner.py`
- 现有 `Agent` 类引用需要迁移

### 风险

- 重构可能引入 behavior 变化 → 全量 195 tests 覆盖
- E2E 验证 kimi + claude native goal 和 goal loop 两边都正常

## 验证

| 项目 | 验证方式 |
|------|---------|
| 功能等价 | 195 tests 全部通过 |
| E2E | kimi/claude 各跑一次 goal mode |
| 代码审查 | `Agent` 类已删除，`agent()` 函数签名不变 |