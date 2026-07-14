---
title: ADR 0030 — DDD 四层架构
description: 将 loopflow 重构为 DDD 四层架构（基础设施/领域/应用/展示），领域层纯粹不依赖任何基础设施
type: adr
status: accepted
created: 2026-07-14T00:00:00Z
---

# ADR 0030: DDD 四层架构

## Context

ADR 0028 引入 Agent 层，ADR 0029 重构为 AgentRunner。但当前代码仍然没有清晰的分层边界：

- `runtime.py` 混杂了基础设施（`_make_backend`、`_run_subagent`、cache）、应用协调（`agent()`、`parallel()`）、展示（`_emit_log`）
- `agent.py` 混杂了领域实体（`AgentDef`）、领域服务（`marshal()` 等）、基础设施（`parse_agent()` 做文件 I/O）
- 领域层 `marshal()` 依赖 `BaseBackend` 类型，违反依赖倒转

## Decision

采用 DDD 四层架构，严格依赖方向：

```
展示层 ──→ 应用层 ──→ 领域层
              │
              └──→ 基础设施层
```

### 依赖规则

| 层 | 可以 import | 不可以 import |
|----|------------|--------------|
| 领域层 | 标准库 + typing | 任何其他三层 |
| 应用层 | 领域层 + 基础设施层 | 展示层 |
| 基础设施层 | 标准库 + 领域层（实体定义） | 应用层、展示层 |
| 展示层 | 应用层 + 领域层（类型） | 基础设施层 |

### 模块结构

```
src/loopflow/
├── domain/                    # 领域层 — 纯粹，零外部依赖
│   ├── __init__.py
│   ├── agent_def.py           # AgentDef 聚合根
│   ├── capabilities.py        # Capabilities 值对象
│   ├── marshalling.py         # marshal() 领域服务
│   └── goal_loop.py           # run_goal_loop() 领域服务
│
├── infrastructure/            # 基础设施层 — 技术实现
│   ├── __init__.py
│   ├── backends/              # BaseBackend, CliBackend, 具体后端
│   │   ├── base.py
│   │   ├── manager.py         # BackendManager: discover(), get(), list()
│   │   ├── kimi.py
│   │   ├── claude.py
│   │   └── ...
│   ├── transports/            # CliTransport, AcpTransport
│   ├── repository.py          # parse_agent(), list_agents() — 文件 I/O
│   ├── context.py             # RunContext, State — session/cache
│   └── worktree.py            # _create_worktree()
│
├── application/               # 应用层 — 协调领域服务 + 基础设施
│   ├── __init__.py
│   ├── runner.py              # AgentRunner
│   └── orchestrator.py        # agent(), parallel(), pipeline(), workflow()
│
└── presentation/              # 展示层 — CLI + display
    ├── __init__.py
    ├── cli.py
    ├── display/
    └── graph.py
```

### 核心设计决策

**1. Backend Capabilities 是静态属性**

```python
# domain/capabilities.py
@dataclass(frozen=True)
class Capabilities:
    """Backend 的静态能力声明。值对象，领域层可依赖。"""
    native_goal: bool = False
    structured_output: bool = False
    native_skills: bool = False

# infrastructure/backends/base.py
class BaseBackend(ABC):
    @property
    def capabilities(self) -> Capabilities:
        return Capabilities()

# infrastructure/backends/kimi.py
class KimiBackend(BaseBackend):
    @property
    def capabilities(self) -> Capabilities:
        return Capabilities(native_goal=True)
```

**2. 领域层 marshal() 不依赖 Backend**

```python
# domain/marshalling.py
def marshal(ad: AgentDef | None, prompt: str, *,
            goal: str | None = None,
            caps: Capabilities,
            **params) -> tuple[str, dict | None, bool]:
    """caps 是值对象，不是 backend 实例"""
    ...

# application/runner.py
class AgentRunner:
    def run(self, prompt, ...):
        caps = self.backend.capabilities
        resolved, schema, native = marshal(self.ad, prompt, goal=goal, caps=caps, ...)
```

**3. 文件 I/O 在基础设施层**

```python
# infrastructure/repository.py
def parse_agent(file_path: str | Path) -> AgentDef:
    """文件 I/O → 基础设施层。返回领域实体。"""
    ...

# application/runner.py
class AgentRunner:
    def run(self, prompt, ...):
        ad = parse_agent(path)  # 应用层调用基础设施
        result = marshal(ad, ...)  # 应用层调用领域服务
```

### BackendManager 收敛后端发现

```python
# infrastructure/backends/manager.py
class BackendManager:
    """后端的注册、发现、创建。消除散落的 _make_backend + diagnostics。"""
    
    def discover(self) -> list[str]:
        """Discover available backends on PATH."""
        ...
    
    def get(self, name: str) -> BaseBackend:
        """Get a backend instance by name."""
        ...
    
    def create(self, name: str, **kwargs) -> BaseBackend:
        """Create a backend instance with handlers."""
        ...
```

### 影响范围

| 当前文件 | 迁移到 |
|----------|--------|
| `agent.py` — AgentDef, GoalBlocked | `domain/agent_def.py` |
| `agent.py` — marshal(), build_goal_steering(), add_goal_to_schema() | `domain/marshalling.py` |
| `agent.py` — run_goal_loop() | `domain/goal_loop.py` |
| `agent.py` — parse_agent(), list_agents() | `infrastructure/repository.py` |
| `agent.py` — extract_json(), validate_json() | `domain/marshalling.py` |
| `runner.py` | `application/runner.py` |
| `runtime.py` — agent(), parallel(), pipeline(), workflow() | `application/orchestrator.py` |
| `runtime.py` — _make_backend() | `infrastructure/backends/manager.py` |
| `runtime.py` — _run_subagent(), mock | `infrastructure/backends/manager.py` |
| `runtime.py` — RunContext, State | `infrastructure/context.py` |
| `runtime.py` — _write_cache, _persist_state | `infrastructure/context.py` |
| `runtime.py` — _create_worktree | `infrastructure/worktree.py` |
| `runtime.py` — _emit_log, _emit_phase, _write_event | `presentation/` |
| `backends/base.py` | `infrastructure/backends/base.py` |
| `backends/*.py` | `infrastructure/backends/` |
| `transports/*.py` | `infrastructure/transports/` |
| `cli.py` | `presentation/cli.py` |
| `display/` | `presentation/display/` |
| `graph.py` | `presentation/graph.py` |

### 向后兼容

```python
# 顶层 import 保持不变，用户代码无需修改
from loopflow.runtime import agent, parallel, pipeline, workflow, phase, log
from loopflow.agent import AgentDef, parse_agent, GoalBlocked
```

通过 `__init__.py` 重导出来维持兼容性。

## Consequences

### 正面

- 领域层纯粹，零基础设施依赖，可独立单元测试
- 新 backend 只需加文件，不改领域层
- 基础设施可替换（如换 transport 协议）
- 各层职责清晰，新人可快速定位代码

### 负面

- 大重构，所有文件移动
- 新增 `__init__.py` 重导出以维持兼容性
- 目录结构变化，需要更新 import 路径

### 风险

- 195 tests 必须全部通过
- import 兼容性需要仔细处理
- 分步实施，每步可验证

## 验证

| 项目 | 验证方式 |
|------|---------|
| 领域层纯度 | `import loopflow.domain` 不触发任何基础设施 import |
| 功能等价 | 195 tests 全部通过 |
| E2E | kimi/claude goal mode 正常 |
| 兼容性 | `from loopflow.runtime import agent` 仍然可用 |