---
title: loopflow Spec
description: loopflow 核心功能规格：Agent 循环编排、运行实例管理、崩溃恢复。CLI 工具，无 API，无 UI。
type: spec
status: active
version: 5
created: 2026-07-07T12:00:00Z
---

# 概要设计

## 一、项目概述

loopflow 是独立的 AI Agent 循环编排工具。以 Agent 为基本单元构建循环工作流。详见 [Vision](../vision.md)。本 Spec 定义 loopflow 的功能范围、用户故事、模块划分、数据模型和业务规则。

本 Spec 不定义：Agent 后端协议（由 subagent-skills 底层库承载）、编码规范（见 CONTRIBUTING.md）、验收标准（见 AC 文档）、技术选型（见 ADR）。

---

## 二、用户故事

| 编号 | 角色 | 需求 | 目的 | 优先级 |
|------|------|------|------|--------|
| US-001 | 开发者 | 用 Python 定义 loop（workflow.py + agent 定义文件） | 编排 Agent 循环工作流，自由控制循环条件、退出逻辑、状态累积 | P0 |
| US-002 | 开发者 | 通过 CLI 运行 loop（`loop run <name>`） | 启动一个运行实例，执行中可查看进度 | P0 |
| US-003 | 开发者 | 崩溃后 resume 运行实例（`loop resume <run-id>`） | 已完成 Agent 调用自动跳过，不重复执行，不丢失进度 | P0 |
| US-004 | 开发者 | 查看运行实例状态（`loop status <run-id>`） | 了解当前进度、各 Agent 调用结果 | P0 |
| US-005 | 开发者 | 列出所有 loop 定义和运行实例（`loop list`） | 管理本地 loop 和运行历史 | P1 |
| US-006 | 开发者 | 停止运行中的实例（`loop stop <run-id>`） | 中断异常或不再需要的运行 | P2 |
| US-007 | 开发者 | 在工作流中并行调用多个 Agent（parallel） | 同一轮迭代内并发审查，提高效率 | P0 |
| US-008 | 开发者 | 在工作流中流水线处理多个 item（pipeline） | 每个 item 独立流经多个 stage，无屏障 | P1 |
| US-009 | 开发者 | 嵌套调用子 workflow（workflow） | 复用已有 loop 定义 | P2 |

---

## 三、模块划分

| 模块 | 提供的能力 | 目录路径 | 优先级 |
|------|-----------|---------|---------|
| CLI | loop run / resume / status / list / stop 命令解析和路由 | `src/loopflow/cli.py` | P0 |
| Workflow Runtime | 加载 workflow.py，提供 agent/parallel/pipeline/phase/log/args/workflow 运行时 API | `src/loopflow/runtime.py` | P0 |
| Backend Layer | 适配 8 种 AI Agent 后端（kimi/claude/codex/pi/opencode/qwen/kiro/gemini），自动检测，支持 CLI/ACP 传输 | `src/loopflow/backends/` | P0 |
| Registry | 运行实例元数据管理（run.json），Agent 调用缓存索引（序号→jsonl 映射），状态追踪 | `src/loopflow/registry.py` | P0 |
| Lock | 文件锁防止同一 session 并发执行 | `src/loopflow/lock.py` | P0 |
| PhaseGraph | phase 转移图数据结构：邻接表、边计数、环检测、快照，纯数据，不依赖渲染 | `src/loopflow/graph.py` | P1 |
| Display | 终端渲染：PhaseGraph → Rich renderable，增量 Live 更新，线性路径/回边/分支三种布局 | `src/loopflow/display/graph_renderer.py` | P1 |
| Loop Discovery | 扫描 `~/.loopflow/loops/` 发现已安装的 loop 定义 | `src/loopflow/discovery.py` | P0 |

---

# 详细设计

## 四、数据模型

### Loop 定义（文件系统）

```
~/.loopflow/loops/<name>/
├── workflow.py              # meta = {...}; def run(agent, parallel, pipeline, phase, log, args, workflow, state)
└── agents/                  # agent 定义文件
    └── <name>.md            # Markdown + YAML frontmatter
```

### workflow.py meta

`meta` 是 workflow.py 的模块级字典，声明 loop 的元信息和预期阶段：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| name | string | required | loop 唯一标识 |
| description | string | required | 简短描述 |
| phases | object[] | optional | 声明的预期阶段列表 |
| phases[].title | string | required | 阶段标题，与 `phase()` 调用对应 |
| phases[].detail | string | optional | 阶段描述，用于 UI 展示 |
| state | object | optional | 声明的持久化状态变量，key 为变量名，value 为默认值。仅支持 JSON 可序列化类型 |
| state.<key> | any | optional | 默认值，类型即约定类型。首次运行时以默认值初始化，每次 agent() 成功后自动持久化 |
| requires | object | optional | workflow 级别的依赖声明 |
| requires.environment | string | optional | 环境声明文件路径（相对路径，如 `environment.yml`）。`loop run` 启动时校验文件存在，不自动激活或安装 |

`meta` 必须是纯字面量（无变量、函数调用、表达式），用于静态发现和进度显示。`phases` 声明预期阶段，运行时 `phase()` 调用锚定到声明上。`state` 声明持久化变量，运行时通过 `state.key` 属性访问，自动保存到 `state.json`。`requires.environment` 声明环境文件，`loop run` 启动时校验存在性，激活由 agent 或用户完成。

### 运行实例（文件系统）

```
~/.loopflow/runs/<run-id>/
├── run.json                 # 元数据
├── state.json               # 工作流状态（meta.state 的运行时快照）
├── events.jsonl             # 全部事件流（phase + agent，按时间序）
└── <seq>.jsonl              # 每个 agent 调用的输出缓存
```

### run.json

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| loop | string | NOT NULL | loop 定义名称 |
| run_id | string | PK | 唯一运行标识 |
| status | string | NOT NULL | running / done / failed / stopped |
| created | ISO 8601 | NOT NULL | 创建时间 |
| args | object | — | 传入 workflow.py 的参数 |
| counter | integer | NOT NULL | 当前 agent 调用序号 |

### Agent 定义文件

Markdown 文件，YAML frontmatter：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| name | string | required | agent 唯一标识 |
| description | string | required | 简短描述 |
| requires.env | string[] | optional | 需要的环境变量 |
| requires.skills | string[] | optional | 需要的 skill 名称列表。仅名称，如 `[git-check, security-scan]`。按 `~/.agents/skills/` → `~/.loopflow/skills/` 顺序查找。后端支持原生 skill 参数时优先使用；否则 loopflow 自动注入到 system prompt（skill 名称+描述+路径） |
| requires.params | string[] | optional | 需要的模板参数。支持两种格式：<br>`- param_name`（必填参数）<br>`- param_name: default_value`（可选参数，含默认值） |
| requires.mcps | string[] | optional | 需要的 MCP server |
| output | object | optional | JSON Schema，定义 agent 的结构化输出格式。与 `requires.params`（输入契约）对称，`output` 是输出契约 |
| body | string | optional | 系统提示词，支持 `{{param}}` 占位符 |

Agent 定义文件通过 `agent_def` 参数引用：`agent("动态指令", agent_def="reader")`。此时 `body` 作为系统提示词（静态背景/约束），prompt 参数作为动态任务指令追加。`requires.params` 中声明的参数通过 `{{param}}` 在 body 中占位，调用时渲染。可选参数未传入时使用默认值；必填参数未传入时抛 `ValueError`。

当 `output` 存在时，`agent()` 自动将其作为 `schema` 使用，返回 `dict` 而非 `str`。workflow 显式传入 `schema=` 时覆盖 `output`（显式优先）。Schema 通过 prompt 注入传递给 agent（追加到 prompt 末尾），agent 被要求返回纯 JSON 对象。未来后端支持 native structured output 时，升级为 function calling 约束。

### Skill 文件

Skill 是 agent 可用的工具指令，以目录形式存储：

```
~/.agents/skills/<name>/
├── SKILL.md                  # skill 定义（YAML frontmatter + body）
```

```
~/.loopflow/skills/<name>/
├── SKILL.md
```

SKILL.md 格式：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| name | string | required | skill 唯一标识 |
| description | string | required | 简短描述，用于 prompt 注入 |
| path | string | optional | 自定义路径，覆盖默认查找 |
| source | string | optional | 安装源（如 `github:owner/repo@ref`），当前仅记录，不自动下载 |
| body | string | optional | skill 指令内容 |

查找优先级：`~/.agents/skills/` → `~/.loopflow/skills/`。先找到的生效。

### Agent 调用缓存（jsonl）

每行一个 JSON 事件，类型包括：

| type | 含义 |
|------|------|
| version | 协议版本 |
| agent_start | agent 调用开始（含 seq, session, phase） |
| agent_text | agent 输出文本 |
| agent_done | agent 调用完成（含 exit_code） |
| agent_error | agent 调用失败 |
| phase | phase 转移（含 title, ts） |

Agent 事件携带 `phase` 字段，记录当前 phase 上下文。agent 事件与 phase 事件按时间序混合写入 events.jsonl，通过 `phase` 字段重建 phase-agent 层级关系。

### events.jsonl

所有事件按时间顺序追加写入，phase 事件与 agent 事件混合。用于 UI 重建执行图和调试。

```jsonl
{"type":"version","version":1}
{"type":"phase","title":"采集","ts":1.23}
{"type":"agent_start","session":"wf_abc_1","seq":1,"phase":"采集"}
{"type":"agent_text","content":"done"}
{"type":"agent_done","exit_code":0}
{"type":"phase","title":"处理","ts":2.45}
{"type":"agent_start","session":"wf_abc_2","seq":2,"phase":"处理"}
{"type":"agent_text","content":"done"}
{"type":"agent_done","exit_code":0}
```

---

## 五、业务规则

| 规则编号 | 描述 | 触发条件 | 约束 |
|----------|------|----------|------|
| BR-001 | 同一 session 不可并发执行 | `loop run` 时检查 lock | 文件锁阻塞，提示已有进程 |
| BR-002 | Resume 时已完成 Agent 调用自动跳过 | `loop resume` 时检查 `<seq>.jsonl` 是否存在且 exit_code=0 | 缓存命中则直接返回，不真正执行 |
| BR-003 | Agent 调用序号严格递增 | 每次 `agent()` 调用时 counter+1 | 序号即缓存 key，不可跳跃 |
| BR-004 | workflow.py 必须定义 `run()` 函数 | 加载 workflow.py 时检查 | 缺少则报错退出 |
| BR-005 | Agent 定义文件必须含 name 和 description | 解析 agent 文件时检查 | 缺少则报错退出 |
| BR-006 | 运行实例目录不可并发修改 | 同一 run_id 不可同时运行 | 通过 run.json 的 status 判断 |
| BR-007 | workflow.py 的 `meta` 必须是纯字面量 | 加载时检查 | 用于拓扑发现和进度显示 |
| BR-008 | Agent 调用 infra 失败抛 AgentError | `agent()` 执行时后端进程非零退出、超时、不可用 | 抛 `AgentError`，workflow 崩溃，resume 重试。业务失败（agent 正常执行完毕但任务未完成）不在 loopflow 层感知 |
| BR-009 | Schema 不匹配时自动重试 | `agent()` 有 schema 但返回的 JSON parse 失败 | 重试最多 `max_retries` 次（默认 3），每次注入"上次格式不对，请按 schema 输出"提醒。超过次数抛 `AgentError` |
| BR-010 | Workflow 状态自动持久化 | `meta.state` 声明后，每次 `agent()` 成功返回 | 将 `state` 对象的当前快照写入 `state.json`。resume 时加载 `state.json`，缺失 key 用 `meta.state` 默认值填充 |
| BR-011 | Worktree 隔离执行 | `agent()` 指定 `isolation="worktree"` | 创建 `.agents/worktrees/lf_<run_id>_<seq>/` git worktree，agent 子进程 cwd 设为其路径。不自动清理。非 git 仓库忽略 |

Agent 隔离层级体系（递进）：

| 层级 | 机制 | 当前状态 |
|------|------|---------|
| 声明层 | `meta.requires.environment` → 环境文件存在性校验 | BR-014 |
| 文件系统 | `isolation="worktree"` → git worktree | BR-011 |
| 环境激活 | `isolation="conda"` → 自动激活 conda 环境 | 未来 |
| 完整隔离 | `isolation="container"` → Docker/Singularity | 未来 |
| BR-012 | Mock 模式 | `--mock <mode>`（bash 或 auto） | bash：把 prompt 当 shell 执行。auto：有 `output` schema 时根据 schema 生成 mock dict（enum 取第一个值，number 取 0，array 取空列表）；无 schema 时返回固定字符串 `"mock response"` |
| BR-013 | Skill 注入 | `agent()` 调用时 `requires.skills` 非空 | 按 `~/.agents/skills/` → `~/.loopflow/skills/` 顺序查找 skill 目录。后端支持原生 skill 参数时优先使用；否则将 skill 名称、描述、路径注入到 system prompt。skill 目录不存在时标记为 `[not found]`，不阻塞运行 |
| BR-014 | 环境文件校验 | `loop run` 启动时 `meta.requires.environment` 存在 | 检查环境文件是否存在（相对于 workflow 目录）。存在则通过，不存在则报错退出。不解析文件内容，不激活环境，不安装依赖 |

---

## 六、UI 约束

不适用。loopflow 是 CLI 工具，无 UI。

---

# 约束

## 七、非功能指标

| 维度 | 指标 | 目标值 |
|------|------|--------|
| 性能 | CLI 启动到开始执行 | < 1s |
| 兼容性 | Python 版本 | 3.10+ |
| 兼容性 | 操作系统 | macOS / Linux |
| 可靠性 | Resume 缓存命中准确性 | 100%（相同 prompt + 相同序号 → 相同结果） |
| 可维护性 | 外部依赖 | 运行时：pyyaml, click, rich；开发：pytest；管理：uv |

---

## 八、依赖项

| 依赖 | 版本 | 用途 |
|------|------|------|
| pyyaml | — | Agent 定义文件 frontmatter 解析 |
| click | — | CLI 命令路由和参数解析 |
| rich | — | TTY 进度渲染 |
| pytest | — | 测试框架（开发依赖） |
| subagent-skills 后端层 | — | 多 Agent 后端的适配器代码（claude/kimi/codex 等），复制到 src/loopflow/backends/ 下 |
| Python 标准库 | 3.10+ | 所有运行时能力（subprocess/threading/json/pathlib/importlib） |

---

## 九、术语表

| 术语 | 定义 |
|------|------|
| Loop | 一个文件夹，包含 workflow.py + agents/，定义了一个 Agent 循环工作流 |
| Run | Loop 的一次执行实例，有唯一 run_id，状态持久化到 runs/<run-id>/ |
| Agent | 一个 Markdown 文件定义的 AI Agent，有名称、能力声明、系统提示词 |
| Agent 调用 | workflow.py 中 `agent("prompt")` 的一次执行，产生一个序号和对应的 jsonl 缓存 |
| Resume | 崩溃恢复机制：重新执行 workflow.py，已完成的 Agent 调用从缓存返回 |
| Backend | Agent 后端的抽象层，适配不同的 CLI Agent（kimi/claude/codex 等） |
| Transport | 与 Backend 通信的方式：CLI（子进程）或 ACP（Agent Communication Protocol） |