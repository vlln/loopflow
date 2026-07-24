---
title: loopflow Spec
description: loopflow 核心功能规格：Agent 循环编排、可校验恢复、attempt 取消与人工介入及本地 WebUI 控制台。
type: spec
status: active
version: 14
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
| US-002 | 开发者 | 通过 CLI 运行 loop（`loopflow run <name>`） | 启动一个运行实例，执行中可查看进度 | P0 |
| US-003 | 开发者 | 失败后以 retry 或 continue 恢复运行实例 | 校验并复用前序成功调用，选择重跑失败 Agent 或恢复其 session 上下文 | P0 |
| US-004 | 开发者 | 查看运行实例状态（`loopflow status <run-id>`） | 了解当前进度、各 Agent 调用结果 | P0 |
| US-005 | 开发者 | 列出所有 loop 定义和运行实例（`loopflow list`） | 管理本地 loop 和运行历史 | P1 |
| US-006 | 开发者 | 取消运行中或等待输入实例的当前 execution attempt（`loopflow stop <run-id>`） | 释放当前执行资源并防止迟到 worker 覆盖取消事实，后续是否恢复由恢复边界决定 | P0 |
| US-007 | 开发者 | 在工作流中并行调用多个 Agent（parallel） | 同一轮迭代内并发审查，提高效率 | P0 |
| US-008 | 开发者 | 在工作流中流水线处理多个 item（pipeline） | 每个 item 独立流经多个 stage，无屏障 | P1 |
| US-009 | 开发者 | 嵌套调用子 workflow（workflow） | 复用已有 loop 定义 | P2 |
| US-010 | 开发者 | 在 agent 调用层设置 goal 反馈循环 | agent 内部自主迭代直到目标完成或阻塞，无需 workflow 层处理重试逻辑 | P1 |
| US-011 | 开发者 | 声明 loop 的触发方式（loop.md frontmatter） | loop 可被 cron、文件监视或手动触发 | P1 |
| US-012 | 开发者 | 通过 `loopflow dispatch` 自动调度待执行任务 | 扫描队列，按优先级取任务，加资源锁后执行 | P1 |
| US-013 | 开发者 | 通过 `loopflow enqueue` 将任务加入队列 | 延迟执行，由 dispatch 统一调度 | P1 |
| US-014 | 开发者 | 同一资源上的 loop 互斥执行 | 防止两个 loop 同时操作同一 repo | P1 |
| US-015 | 开发者 | 通过 `loop.md` 了解 loop 的目的、流程、权限边界 | 人类和 Agent 无需读 workflow.py 即可理解 loop | P2 |
| US-016 | 开发者 | 在本地 WebUI 的常驻 Runs 列表中切换运行实例 | 不离开工作台即可比较状态并定位当前 Run | P0 |
| US-017 | 开发者 | 查看 Run 的 Phase 路径、循环、分支和并行调用 | 理解工作流当前进度及历史执行路径 | P0 |
| US-018 | 开发者 | 选择一次 Phase 执行并查看其 Agent 调用和事件 | 区分循环中同名 Phase 的不同轮次，定位该次执行的行为与结果 | P0 |
| US-019 | 开发者 | 实时查看所选 Phase 的 Agent 运行过程 | 观察消息、工具调用、重试、错误和最终输出 | P0 |
| US-020 | 开发者 | 在 Loops 工作区浏览 Loop 声明和目录内容 | 无需离开控制台即可检查 loop.md、workflow.py 和 Agents | P1 |
| US-021 | 开发者 | 在 Backends 工作区检查当前环境的后端可用性和诊断日志 | 在运行 Loop 前发现安装、版本或配置问题 | P1 |
| US-022 | 开发者 | 从 WebUI 启动、停止和恢复 Run | 用图形界面完成核心运行管理操作 | P1 |
| US-023 | 开发者 | workflow 阻塞时查看并回答结构化问题 | 不依赖常驻进程介入运行，并在回答后继续同一 Run | P0 |
| US-024 | 开发者 | 明确选择失败 Agent 的 retry 或 continue 恢复方式 | 根据任务副作用和上下文价值控制恢复行为 | P0 |
| US-025 | 开发者 | 在 workflow 或 Agent 定义变化时阻止错误缓存命中 | 避免把旧调用结果或 session 注入语义不同的新调用 | P0 |
| US-026 | 开发者 | 创建 Run 时显式指定工作目录 | WebUI 常驻 server 下让不同 run 在各自项目目录执行和观察，互不污染 | P0 |

---

## 三、模块划分

| 模块 | 提供的能力 | 目录路径 | 优先级 |
|------|-----------|---------|---------|
| CLI | loopflow run / recover / respond / status / list / stop 命令解析和路由 | `src/loopflow/presentation/cli.py` | P0 |
| Workflow Runtime | 加载 workflow.py，提供 agent/parallel/pipeline/phase/intervene/log/args/workflow 运行时 API，支持 goal 反馈循环和确定性重放 | `src/loopflow/runtime.py` | P0 |
| Agent | Agent = Backend + Capabilities：能力声明（skills/schema/goal/model）的 marshalling，遵循"尽力而为"原则（backend 原生支持优先，否则框架降级） | `src/loopflow/agent.py` | P0 |
| Backend Layer | 适配 8 种 AI Agent 后端，默认 CLI 传输，输出归一化为 ACP 兼容事件 | `src/loopflow/backends/` | P0 |
| Lock | 文件锁防止同一 session 并发执行 | `src/loopflow/lock.py` | P0 |
| PhaseGraph | phase 转移图数据结构：邻接表、边计数、环检测、快照，纯数据，不依赖渲染 | `src/loopflow/graph.py` | P1 |
| Display | 终端渲染：PhaseGraph → Rich renderable，增量 Live 更新，线性路径/回边/分支三种布局 | `src/loopflow/display/graph_renderer.py` | P1 |
| Loop Discovery | 扫描 `~/.loopflow/loops/` 发现已安装的 loop 定义，读取 `loop.md` 获取元数据，提取 `workflow.py` 的 `meta.phases` 声明 | `src/loopflow/discovery.py` | P0 |
| Dispatch | 扫描队列、按优先级排序、资源锁检查、执行 loopflow run | `src/loopflow/dispatch.py` | P1 |
| Queue | 队列读写（enqueue、dequeue、list），文件持久化在 `~/.loopflow/queue/` | `src/loopflow/queue.py` | P1 |
| Web Application | 提供 Loop、Run、Phase、Agent Call、Intervention、Backend 的查询模型及 run/stop/recover/respond 应用命令，供 CLI 与 Web 复用 | `src/loopflow/application/` | P0 |
| Web API | 提供本机 HTTP 查询、命令接口和 Run 事件流，不直接实现领域逻辑 | `src/loopflow/presentation/web/` | P0 |
| Web Frontend | 提供 Runs、Loops、Backends 三个主从工作区，消费 Web API 与事件流 | `web/` | P0 |
| File Observation | phase 边界快照 diff，记录工作目录文件变化到 `file_changes.jsonl`，不参与业务事件流和重放 | `src/loopflow/file_observation.py` | P2 |

---

# 详细设计

## 四、数据模型

### 文件系统布局

```
pwd (工作目录)                          ~/.loopflow/ (loopflow 数据目录)
├── .agents/                           ├── runs/
│   └── worktrees/                     │   ├── runs_index.jsonl
│       └── lf_<uuid>_<seq>/           │   └── lf_<pwd-path>/
│           (worktree 隔离，BR-011)     │       └── <uuid>/
│                                      │           (运行实例，见下文)
│                                      └── loops/
│                                          ├── .<name>/    (可下载/可恢复)
│                                          └── <name>/     (分发用声明)
```

`pwd` 是工作目录，`loopflow run` 在此目录下运行 workflow。worktree 隔离在 `pwd/.agents/worktrees/` 下创建，属于项目级资源。`~/.loopflow/runs/` 存储 loopflow 内部运行时状态（类比实例化内存数据），`~/.loopflow/loops/` 存储 workflow 定义。runs 按 `lf_<pwd-path>` 分组，其中 `<pwd-path>` 是工作目录的绝对路径，`/` 替换为 `-`。

`runs/runs_index.jsonl` 保存无损定位映射，每个 Run 一行，字段固定为 `working_directory`（真实绝对工作目录）、`runs_directory`（`lf_<pwd-path>` 分组目录的绝对路径）和 `run_id`。创建 Run 时追加记录；读取旧 Run 或遇到缺失、损坏的索引记录时，允许回退到目录扫描及 `lf_<pwd-path>` 分组名。

### Loop 定义（文件系统）

```
~/.loopflow/loops/<name>/
├── loop.md                  # 声明式定义（新增）：frontmatter + body
├── workflow.py              # meta = {...}; def run(agent, parallel, pipeline, phase, log, args, workflow, state)
├── agents/                  # agent 定义文件
│   └── <name>.md            # Markdown + YAML frontmatter
├── pixi.toml                # 可选：环境声明（推荐）
└── .skills/                  # 可选：项目隔离的 skill 目录
```

### loop.md（新增）

Loop 的声明式定义文件，YAML frontmatter + Markdown body。Frontmatter 是机器可读的结构化元数据，body 是人类和 Agent 可读的文档。

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

**`state` 不属于 loop.md。** workflow 的内部状态（重试计数、阶段标记等）是编排层的实现细节，保持在 `workflow.py` 的 `meta.state` 中。loop.md 只声明调度层关心的内容：身份、触发方式、资源需求。

Body 是 Markdown 格式，内容自由但建议包含：目的、流程、权限边界、升级条件。

### 队列条目（文件系统）

```
~/.loopflow/queue/
└── <uuid>.json              # 每个待执行任务是一个 JSON 文件
```

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| loop | string | NOT NULL | loop 名称 |
| args | object | — | 传入 workflow.py 的参数 |
| resources | object | — | 资源声明，key 为资源类型，value 为资源标识 |
| priority | integer | NOT NULL | 优先级，数字越小越优先 |
| created | ISO 8601 | NOT NULL | 创建时间 |

### 资源锁（文件系统）

```
~/.loopflow/locks/
└── <resource-type>-<sha256(resource-value)[:16]>.lock
```

锁文件包含 PID 和时间戳。TTL 30 分钟，超时自动清理。

- `.` 前缀的 loop 目录名（如 `.bio-reproducer`）表示可下载/可恢复的 loop，自带完整环境
- 非 `.` 前缀的 loop 目录名（如 `my-workflow`）表示分发用的纯声明 loop，依赖外部环境

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
| requires.environment | string | optional | 环境声明文件路径（相对路径，如 `environment.yml` 或 `pixi.toml`）。`loopflow run` 启动时校验文件存在，不自动激活或安装。推荐使用 pixi（原生支持 skill 隔离和 npm 依赖），但 loopflow 不约束文件格式 |

`meta` 必须是纯字面量（无变量、函数调用、表达式），用于静态发现和进度显示。`phases` 声明预期阶段，运行时 `phase()` 调用锚定到声明上。`state` 声明持久化变量，运行时通过 `state.key` 属性访问，自动保存到 `state.json`。`requires.environment` 声明环境文件，`loopflow run` 启动时校验存在性，激活由 agent 或用户完成。

### 运行实例（文件系统）

```
~/.loopflow/runs/lf_<pwd-path>/<uuid>/
├── run.json                 # 元数据
├── state.json               # 工作流状态（meta.state 的运行时快照）
├── events.jsonl             # 全部事件流（phase + agent，按时间序）
├── interventions/           # 原子持久化的人工输入请求与响应
│   └── <request-id>.json
└── <call-id>.jsonl          # 每个 Agent Call 的输出缓存；顶层顺序 ID 与旧 seq 相同
```

`<pwd-path>` 是工作目录的绝对路径，`/` 替换为 `-`。例如 `pwd=/Users/vlln/projects/myapp` → `lf_Users-vlln-projects-myapp`。`<uuid>` 是 `uuid.uuid4().hex`，每次 `loopflow run` 生成唯一标识。

### runs_index.jsonl

```json
{"working_directory":"/Users/vlln/projects/myapp","runs_directory":"/Users/vlln/.loopflow/runs/lf_Users-vlln-projects-myapp","run_id":"<uuid>"}
```

三个字段均为必填字符串。索引采用只追加 JSONL；同一 `run_id` 出现多次时以最后一条有效记录为准。`runs_directory` 必须位于当前配置的 runs 根目录内，才能用于 Run 定位。

### run.json

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| loop | string | NOT NULL | loop 定义名称 |
| run_id | string | PK | 唯一运行标识 |
| status | string | NOT NULL | running / waiting_input / cancelling / cancelled / done / failed；stopped 仅 legacy 可读 |
| created | ISO 8601 | NOT NULL | 创建时间 |
| args | object | — | 传入 workflow.py 的参数 |
| counter | integer | NOT NULL | 当前 agent 调用序号 |
| started_at | ISO 8601 | optional | 进程实际开始时间；旧 Run 可缺失 |
| finished_at | ISO 8601 | optional | done / failed / cancelled 的结束时间 |
| updated_at | ISO 8601 | optional | 最近一次元数据更新；用于列表刷新 |
| pid | integer | optional | 当前执行子进程 PID；仅用于进程管理，必须结合进程启动标识校验 |
| process_started_at | ISO 8601 | optional | PID 对应进程的启动时间，用于防止 PID 复用误判 |
| current_phase | string | optional | 最近一次 phase 事件的 title |
| error_summary | string | optional | failed 状态的短错误摘要，不替代完整事件 |
| execution_epoch | integer | NOT NULL | 每次首次执行或恢复递增；worker 写状态时的 fencing token |
| execution_options | object | NOT NULL | 首次执行冻结的有效 backend、model、mock、phase 范围等选项；recover 不接受覆盖 |
| cancel_point | string | optional | 最近一次取消点：worker_running / no_worker_running；仅用于派生恢复动作，不表示用户放弃 Run |
| active_call_id | string | optional | 最近一次执行中的 Agent Call；worker_running 取消或 failed 时用于定位 retry/continue 目标 |
| active_worker_atomic | boolean | optional | active worker 是否处于原子提交/隔离边界；true 时 recover_continue 不可用 |

### Intervention

每个请求使用独立 JSON 文件并原子替换，避免服务重启后丢失或读取半写内容：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| request_id | string | required | Run 内唯一请求 ID |
| key | string | required | workflow 重放路径中稳定且唯一的键 |
| prompt | string | required | 向人类展示的问题 |
| schema | object/null | required | 回答 JSON Schema；null 表示任意 JSON 值 |
| call_id | string/null | required | 关联 Agent Call；workflow 直接请求时为 null |
| session_id | string/null | required | 可继续的 backend session |
| resume_mode | string | required | replay（workflow 请求）/ continue（Agent 请求） |
| status | string | required | pending / answered / closed；stop waiting_input 不关闭 pending request，closed 仅用于显式废弃或 legacy 读取 |
| response | any | optional | immutable 回答，仅 status=answered 时存在 |
| created_at | ISO 8601 | required | 请求创建时间 |
| responded_at | ISO 8601/null | required | 回答时间 |

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
| body | string | optional | skill 指令内容 |

查找优先级：`~/.agents/skills/` → `~/.loopflow/skills/`。先找到的生效。

Skill 的安装来源（WHERE）不在 SKILL.md 中声明，由环境文件（`pixi.toml` 或 `environment.yml`）管理。loopflow 不约束使用哪个 skill 管理器（skit、skill.sh、npm 等）。

### Agent 调用缓存（jsonl）

缓存事件格式以 ACP `SessionNotification` 为标准化基础，去掉 JSON-RPC 信封，扁平化存储。`<call-id>.jsonl` 是 recover 缓存契约，不使用 Web 事件信封。顶层顺序 Call 继续使用四位序号文件名；并行子 Call 使用层级 call-id 文件名：

| type | 含义 | 来源 |
|------|------|------|
| `agent_start` | agent 调用开始（含 call_id、input_digest、phase） | loopflow 特有 |
| `agent_session` | backend session ID 首次可用（含 call_id、session_id） | loopflow 特有 |
| `agent_thought_chunk` | agent 思考过程 | ACP `agent_thought_chunk` |
| `agent_message_chunk` | agent 文本输出（实时追加，流式 chunk） | ACP `agent_message_chunk` |
| `tool_call` | 工具调用开始 | ACP `tool_call_start` |
| `tool_call_update` | 工具调用进度/完成 | ACP `tool_call_progress` |
| `usage_update` | token 用量 | ACP `usage_update` |
| `agent_done` | agent 调用完成（含 call_id、status、session_id、exit_code、duration_ms） | loopflow 特有 |
| `agent_error` | agent 调用失败 | loopflow 特有 |
| `phase` | phase 转移（含 title, ts） | loopflow 特有 |

新写入缓存以 `call_id` 标识逻辑调用，以 `input_digest` 校验规范化调用输入。digest 覆盖 workflow.py 内容摘要、最终 user/system prompt、输出 schema、backend、model、Agent 定义和影响调用语义的执行选项。密钥和环境变量值不得写入 digest 原文或缓存。

`<call-id>.jsonl` 缓存文件在 agent 执行期间**实时追加**事件，获得 backend session ID 时立即追加 `agent_session`，完成后写入 `agent_done`。恢复缓存命中要求 call_id 和 input_digest 均匹配，且存在 `agent_done(status=succeeded, exit_code=0)`；否则不得返回成功缓存。旧缓存缺少新字段时只允许 unverified legacy retry。

同一 Call 的 retry 以新的 `agent_start` 开始生命周期段，continue 以 `agent_resume` 开始。缓存 reader 只在一个段内匹配 digest、提取消息和完成标记，不跨段拼接失败输出。

`parallel()` 和 `pipeline()` 在启动线程前按输入位置预分配稳定 call_id，线程完成顺序不得影响逻辑身份。

CLI 后端将其原生输出转换为 ACP 兼容事件后写入缓存。未来 ACP 后端直接透传 `SessionNotification`。

### events.jsonl

所有事件按时间顺序追加写入，phase 事件与 agent 事件混合。用于 UI 重建执行图和调试。新写入 `events.jsonl` 的事件使用统一信封；运行时将缓存/后端事件写入 `events.jsonl` 时完成信封转换。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| version | integer | required | 事件 schema 版本 |
| event_id | integer | required | Run 内严格递增的事件序号 |
| type | string | required | 事件类型 |
| ts | ISO 8601 | required | 事件产生时间 |
| run_id | string | required | 所属 Run |
| phase | string | optional | 所属 Phase title，用于聚合执行图 |
| phase_id | string | optional | 一次 Phase occurrence 的稳定标识；phase 和 Agent 事件必填 |
| call_id | string | optional | 所属 Agent Call 的稳定标识；Agent 事件必填 |
| payload | object | required | 事件类型专属数据 |

`phase` title 对应聚合执行图中的节点；`phase_id` 对应一次实际进入该 Phase 的 occurrence。例如 `Review → Fix → Review` 只有两个聚合节点，但有三个 phase_id。用户选择聚合节点时可查看全部 occurrence，选择某个 occurrence 后只展示该次执行关联的 Calls 和 Events。

新事件示例：

```jsonl
{"version":2,"event_id":1,"type":"phase","ts":"2026-07-18T20:00:00Z","run_id":"abc","phase":"采集","phase_id":"phase-1","payload":{"title":"采集","occurrence":1}}
{"version":2,"event_id":2,"type":"agent_start","ts":"2026-07-18T20:00:01Z","run_id":"abc","phase":"采集","phase_id":"phase-1","call_id":"call-1","payload":{"session":"wf_abc_1"}}
{"version":2,"event_id":3,"type":"agent_message_chunk","ts":"2026-07-18T20:00:02Z","run_id":"abc","phase":"采集","phase_id":"phase-1","call_id":"call-1","payload":{"content":"开始处理..."}}
{"version":2,"event_id":4,"type":"agent_done","ts":"2026-07-18T20:00:03Z","run_id":"abc","phase":"采集","phase_id":"phase-1","call_id":"call-1","payload":{"exit_code":0,"duration_ms":2000}}
```

没有 `version` 信封的历史 `events.jsonl` 视为 `legacy`。Legacy reader 保证原始事件时间线可读，并尽力恢复聚合 Phase 图；只有具备明确 session/phase 证据时才建立 Call 或 Phase occurrence 关联。并行交错或证据不足的事件标记为 `unattributed`，不得按文件位置虚构归属。

### file_changes.jsonl

工作目录文件变化观察数据，按 Phase 边界快照 diff 采集。与 `events.jsonl` 严格分离——不参与业务事件流、不参与确定性重放。通过 SSE `file_changes` topic 实时推送（详见 [ADR-0039](../adr/0039-file-change-observation.md) 和 [ADR-0041](../adr/0041-sse-multi-topic-transport.md)）。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| seq | integer | required | Run 内从 1 开始严格递增的序号，作为 SSE `file_changes` topic 的游标（详见 [ADR-0041](../adr/0041-sse-multi-topic-transport.md)） |
| phase | string | required | 产生这些变化的 Phase title |
| phase_id | string | required | 对应的 Phase occurrence 标识，与 events.jsonl 中的 phase_id 一致 |
| ts | ISO 8601 | required | 快照拍摄时间 |
| changes | object[] | required | 文件变化列表 |
| changes[].path | string | required | 相对 pwd 的文件路径 |
| changes[].action | string | required | `created` / `modified` / `deleted` |
| changes[].size | integer | created/modified 时必填 | 变化后的文件大小（bytes） |
| changes[].prev_size | integer | modified/deleted 时必填 | 变化前的文件大小（bytes） |

采集时机：每次 `phase()` 调用时对 pwd 拍摄快照，与上一个快照 diff，记录该 Phase 期间的文件变化。首次 `phase()` 调用和 Run 启动时建立基线快照，不产生 diff。

扫描范围：pwd 下所有文件，排除 `.agents/worktrees/`、`.git/`、`__pycache__/`、`.pyc`。`meta.file_observation.exclude` 可声明额外排除路径（glob 模式）。`meta.file_observation.enabled` 设为 `false` 可禁用观察（默认 `true`）。

无 `file_changes.jsonl` 的 Run（legacy 或禁用）在 WebUI 显示空状态，不报错。

---

## 五、业务规则

| 规则编号 | 描述 | 触发条件 | 约束 |
|----------|------|----------|------|
| BR-001 | 同一 session 不可并发执行 | `loopflow run` 时检查 lock | 文件锁阻塞，提示已有进程 |
| BR-002 | 恢复时前序成功 Agent Call 可校验重放 | recover 检查 `<call-id>.jsonl` | call_id/input_digest 相同且存在 succeeded/exit_code=0 提交标记时返回缓存；digest 不同报 replay_diverged |
| BR-003 | Agent Call ID 稳定 | 分配顺序或并行调用身份 | 顺序调用严格递增；parallel/pipeline 在线程启动前按输入位置预分配子 ID，完成顺序不改变 ID |
| BR-004 | workflow.py 必须定义 `run()` 函数 | 加载 workflow.py 时检查 | 缺少则报错退出 |
| BR-005 | Agent 定义文件必须含 name 和 description | 解析 agent 文件时检查 | 缺少则报错退出 |
| BR-006 | 运行实例目录不可并发执行 | 同一 run_id 首次执行、恢复、停止或回答 | 使用 Run 独占锁和递增 execution_epoch；旧 worker 不得写入新 epoch 的状态 |
| BR-007 | workflow.py 的 `meta` 必须是纯字面量 | 加载时检查 | 用于拓扑发现和进度显示 |
| BR-008 | Agent 调用 infra 失败抛 AgentError | `agent()` 执行时后端进程非零退出、超时、不可用 | 持久化 failed Call 及已知 session_id 后抛 `AgentError`；Run 可选择 retry 或满足能力条件时 continue |
| BR-009 | Schema 不匹配时自动重试 | `agent()` 有 schema 但返回的 JSON parse 失败 | 重试最多 `max_retries` 次（默认 3），每次注入"上次格式不对，请按 schema 输出"提醒。超过次数抛 `AgentError` |
| BR-010 | Workflow 状态投影与重放分离 | `meta.state` 声明、Agent 成功或 recover | 运行时将当前快照写入 state.json；recover 从 meta.state 默认值重放并重新计算，不以旧 state.json 为起点 |
| BR-011 | Worktree 隔离执行 | `agent()` 指定 `isolation="worktree"` | 在 `pwd/.agents/worktrees/lf_<uuid>_<call-id>/` 创建 git worktree，agent 子进程 cwd 设为其路径。不自动清理。非 git 仓库忽略 |

Agent 隔离层级体系（递进）：

| 层级 | 机制 | 当前状态 |
|------|------|---------|
| 声明层 | `meta.requires.environment` → 环境文件存在性校验 | BR-014 |
| 文件系统 | `isolation="worktree"` → git worktree | BR-011 |
| 环境激活 | `isolation="conda"` → 自动激活 conda 环境 | 未来 |
| 完整隔离 | `isolation="container"` → Docker/Singularity | 未来 |

| 规则编号 | 描述 | 触发条件 | 约束 |
|----------|------|----------|------|
| BR-012 | Mock 模式 | `--mock <mode>`（bash 或 auto） | bash：把 prompt 当 shell 执行。auto：有 `output` schema 时根据 schema 生成 mock dict（enum 取第一个值，number 取 0，array 取空列表）；无 schema 时返回固定字符串 `"mock response"` |
| BR-013 | Skill 注入 | `agent()` 调用时 `requires.skills` 非空 | 按 `~/.agents/skills/` → `~/.loopflow/skills/` 顺序查找 skill 目录。后端支持原生 skill 参数时优先使用；否则将 skill 名称、描述、路径注入到 system prompt。skill 目录不存在时标记为 `[not found]`，不阻塞运行 |
| BR-014 | 环境文件校验 | `loopflow run` 启动时 `meta.requires.environment` 存在 | 检查环境文件是否存在（相对于 workflow 目录）。存在则通过，不存在则报错退出。不解析文件内容，不激活环境，不安装依赖 |
| BR-015 | Agent 输出实时可见 | `agent()` 执行期间 | `text_handler` 流式写入时同步 append `agent_message_chunk` 事件到 `<call-id>.jsonl` 和 `events.jsonl`。完成后写入 `agent_done`。用户可读取该 Call 缓存实时查看进度 |
| BR-016 | 缓存事件 ACP 归一化 | `agent()` 执行时 | CLI 后端将原生输出转换为 ACP `SessionNotification` 兼容事件（`agent_message_chunk`/`agent_thought_chunk`/`tool_call`/`tool_call_update`/`usage_update`）。未来 ACP 后端直接透传 |
| BR-017 | Goal 反馈循环 | `agent()` 调用时 `goal` 参数非空 | 框架进入 goal 模式：内部循环调用 agent，每次迭代复用同一 session（首次 create，后续 resume）。Agent 通过 `__goal.status` 声明状态（active/complete/blocked）。complete 时剥离 `__goal` 返回业务 result。同一 reason 连续 3 次 blocked 抛 `GoalBlocked`。达到 `goal_max_iterations`（默认 10）抛 `GoalBlocked`。`__goal` schema wrapper 由框架自动注入和剥离，对业务层透明 |
| BR-018 | loop.md 为元数据权威源 | discovery 扫描 loop 时 | 优先读取 `loop.md` 的 frontmatter。`loop.md` 不存在时回退到 `workflow.py` 的 `meta` 字典 |
| BR-019 | 队列任务不可并发执行同一资源 | `loopflow dispatch` 时检查资源锁 | 同一 resource 同时只能有一个 loop 运行。加锁失败则跳过该任务，留在队列 |
| BR-020 | dispatch 幂等 | 每次 `loopflow dispatch` 调用 | 扫描全部队列文件，逐个尝试加锁执行。锁文件 TTL 30 分钟，超时自动清理 |
| BR-021 | 手动触发不经队列 | `loopflow run <name>` | 直接执行，不经过队列。`loopflow enqueue` 写入队列，由 `loopflow dispatch` 统一调度 |
| BR-022 | 队列优先级 | 队列中有多个任务时 | 按 priority 升序 → created 升序排列。不抢占正在运行的 loop |
| BR-023 | WebUI 仅提供本地控制台 | 启动 Web 服务 | 默认只绑定 `127.0.0.1`；非本机绑定必须显式配置，首版不提供多用户认证 |
| BR-024 | Runs 使用常驻主从工作台 | 用户进入 WebUI 或切换 Run | 左侧保留可筛选的 Runs 列表，右侧原地切换所选 Run，不设置独立的 Runs 列表页跳转流程 |
| BR-025 | Phase、state、Run status 分层展示 | 构建 Run 读模型 | Phase 表示执行路径；state 表示 `state.json` 当前投影；Run status 表示 running/waiting_input/cancelling/cancelled/done/failed，三者不得混用 |
| BR-026 | Phase occurrence 详情只展示有证据的数据 | 用户选择聚合 Phase 或一次 occurrence | occurrence 由 `phase_id` 区分，Agent Calls 和 events 由 `phase_id`/`call_id` 关联；首版不承诺 Phase input/output/state diff，不从日志文本推断 |
| BR-027 | Run 操作受状态和恢复边界约束 | WebUI 请求 run/stop/recover/respond/reconcile | running 允许 stop；waiting_input 允许 respond 或 stop；failed 允许 recover；cancelled 在存在可重放边界时允许 recover，在存在 pending intervention 时允许 respond；done/legacy stopped 不允许 recover；stale 只允许 reconcile；rerun 是创建新 Run 的便利动作，不作为旧 Run 状态转换；非法转换返回冲突错误且不修改文件 |
| BR-028 | Loop 文件预览限制在 Loop 根目录 | WebUI 请求 Loop 文件 | 解析后的真实路径必须位于所选 Loop 根目录内；拒绝路径穿越、符号链接逃逸和任意绝对路径 |
| BR-029 | Run 事件流可断线恢复 | WebUI 订阅 Run | 客户端按 event_id 请求断点后的事件；服务端可重放已持久化事件并继续推送新增事件，重复连接不得重复执行 Run |
| BR-030 | Backend 诊断基于真实能力 | WebUI 查询后端 | 仅展示 BackendManager 或诊断命令可观测的安装、版本、能力、transport 和日志；不得伪造 VRAM、延迟或健康分数 |
| BR-031 | Run 与 state 文件原子更新 | 创建 Run、状态变化、Phase 变化、state 持久化或进程退出 | `run.json` 和 `state.json` 各自在同目录写临时文件，flush 后独立原子替换，不承诺跨文件事务；仅替换 run.json 时在同一份新 JSON 中更新其 updated_at，state.json 不增加保留字段 |
| BR-032 | 陈旧 running 状态可识别和修复 | 读取或 reconcile status=running 的 Run | 读取时同时校验 pid 和 process_started_at；进程不存在或启动标识不匹配时，读模型返回 stale 且不修改文件。显式 reconcile 再次校验后原子写 status=failed、finished_at、updated_at 和 error_summary，清除 pid/process_started_at，随后允许 recover |
| BR-033 | 恢复模式显式选择 | failed/cancelled Run 执行 recover | retry/replay 是默认恢复路径，创建新 session 或重放到 pending 边界；continue 使用原 session_id；缺少 durable session 能力、目标 Call 未落盘 session_id 或 active worker 为原子/隔离边界时返回 continue_not_supported，不静默降级 |
| BR-034 | stop 取消当前 execution attempt | running/waiting_input Run 执行 stop | 先持久化取消意图，再终止已验证身份的进程组；SIGTERM 超时后 SIGKILL；最终 cancelled；cancelled 表示本次 execution epoch 被取消，不表示 Run identity 不可恢复 |
| BR-035 | 人工介入可持久化重放 | workflow 调用 intervene 或 Agent 返回结构化 requests | 创建 request 后 Run 进入 waiting_input 且 worker 退出；workflow `intervene()` 是 routing/control gate，通过 replay 返回回答给 workflow；Agent requests 是继续执行所需输入，仅在 durable session 已落盘时创建并通过 continue 返回给 Agent；waiting_input 被 stop 后 pending request 保留，respond 可恢复同一 Run |
| BR-036 | Intervention 不从自然语言推断 | Agent 输出问题文本 | 仅结构化 `__loopflow.status=waiting_input` 且含 requests 的 control output 触发 waiting_input；普通文本按 Agent 结果处理 |
| BR-037 | 回答只提交一次 | pending intervention 接收 response | options/custom 校验通过后原子写 answered；后续提交返回 intervention_already_answered，不覆盖 response 或重复恢复 |
| BR-038 | 首次执行冻结恢复选项 | 创建 Run | 将自动选择后的有效 backend/model 和其他执行选项写入 run.json；recover 沿用且不接受覆盖 |
| BR-039 | CLI resume 是 deprecated recover retry 别名 | failed/cancelled Run 调用旧 CLI resume | 执行 recover --mode retry 并输出弃用提示；Web API 不保留 resume 端点；legacy stopped 仍拒绝 |
| BR-040 | Workflow 满足确定性重放契约 | 首次执行和 recover | Call 路径只能稳定依赖 args、缓存 Agent 结果、Intervention 回答和确定性 Python；时间、随机数、变化的环境或实时外部读取不得直接决定路径 |
| BR-041 | Recover 必须到达目标 | workflow 重放 | 到达预期失败 Call/Intervention 前出现不同 Call、digest 不同或提前结束均报 replay_diverged，不得标记 done |
| BR-042 | Declared phases 预显示 | Run 创建时 Loop 含 `meta.phases` 声明 | 从 declared phases 生成占位节点（pending 状态），运行时按 title 匹配合并 runtime events；无声明时退化为运行时涌现；详见 [ADR-0040](../adr/0040-declared-phases-predisplay.md) |
| BR-043 | 工作目录文件变化观察 | `phase()` 调用时且 `meta.file_observation.enabled` 非 false | 对 run 的工作目录（BR-044）拍摄快照并与上一快照 diff，追加到 `file_changes.jsonl`（含 `seq` 序号）；不写入 events.jsonl、不参与重放；通过 SSE `file_changes` topic 推送（ADR-0041）；详见 [ADR-0039](../adr/0039-file-change-observation.md) |
| BR-044 | Run 显式工作目录 | `POST /runs` 携带 `working_directory` 时 | 必须是已存在目录的绝对路径（否则 422 `validation_failed`）；executor 子进程 chdir 到该目录执行 workflow 与文件观察；缺省为进程 cwd（向后兼容）；持久化到 run.json，recover/rerun 沿用；详见 [ADR-0042](../adr/0042-run-working-directory.md) |
| BR-045 | 文件观察基线快照 | Run 启动时且观察启用 | 先建立基线快照（内存态，不产生记录），phase diff 针对基线或上一快照；`created` 仅表示 phase 期间新建，预先存在的文件首改标记 `modified`；详见 [ADR-0043](../adr/0043-file-observation-baseline.md) |

Agent 结构化 intervention 控制结果固定为：

```json
{
  "__loopflow": {
    "status": "waiting_input",
    "requests": [
      {
        "key": "scope",
        "prompt": "本轮是否扩大搜索范围？",
        "options": ["扩大", "不扩大"],
        "allow_custom": false
      }
    ]
  }
}
```

`status` 固定为 `waiting_input`。`requests` 为非空数组；每个 request 的 `key` 和 `prompt` 为非空字符串，`options` 为 string array，`allow_custom` 为 boolean。response 统一为 string；`allow_custom=false` 时 response 必须属于 options，`allow_custom=true` 时可以是任意非空 string。该控制对象不作为业务结果返回给 workflow；满足 durable session 条件时转为 Intervention，否则 Call 失败。

---

## 六、UI 约束

WebUI 是本地开发者控制台，视觉规范以 [`references/DESIGN.md`](../../references/DESIGN.md) 为唯一权威源。本节定义信息架构和行为边界，不重复颜色、字体、圆角和间距 token。

### 一级工作区

| 工作区 | 主列表 | 详情区域 | 核心操作 |
|--------|--------|----------|----------|
| Runs | 常驻 Runs 列表，支持状态、Loop 和文本筛选 | Phase 路径、Phase 详情、Agent 过程和待回答 Intervention | run / stop / recover / respond / rerun |
| Loops | 已发现的 Loop 声明列表 | loop.md 渲染、workflow.py、Agents、允许范围内的文件、关联 Runs | run / enqueue |
| Backends | Backend 列表及可用状态 | capabilities、CLI 路径、版本、transport、诊断日志 | 执行诊断 |

Queue 首版作为 Runs 工作区内的 `Runs / Queue` 模式，不设一级导航；当调度功能扩展后可通过新 Spec 提升为一级工作区。

### Runs 工作台

1. 左栏是常驻 Runs 列表，不使用独立列表页作为进入详情的前置步骤。
2. 中间上方展示 Phase 执行路径；必须表达回边次数、分支、当前路径和并行调用，不得退化为固定线性步骤条。Run 创建后若 Loop 含 `meta.phases` 声明，立即显示占位 phase 节点（pending 状态），运行时按 title 匹配合并实际 events；无声明时从空白开始按 events 涌现。占位节点、实际节点和 undeclared 节点有明确视觉区分。
3. 中间下方展示所选 Phase occurrence 的 Calls / Events；Run 当前 state 作为 Run 级 Inspector 信息展示，不伪装成 Phase state。Phase input/output/state diff 留待未来 observation 事件支持。
4. 右栏展示所选 Phase 的运行过程，并可进一步选择 Agent Call 查看消息、工具调用、重试、错误、输出和原始事件。
5. 切换 Run 或 Phase 时保留列表筛选和布局尺寸；实时事件不得引发布局跳动。
6. failed/cancelled Run 明确提供可用的 Recover/Retry 与 Continue 操作；Continue 不可用时展示后端能力、session 持久化或原子 worker 边界原因，不静默执行 Retry。
7. waiting_input Run 展示结构化 prompt 和匹配 schema 的输入控件；回答只提交一次，提交期间禁用重复操作。
8. Phase 详情下方展示该 Phase 期间工作目录的文件变化列表（created/modified/deleted），按 SSE `file_changes` topic 推送的数据渲染。无文件变化的 Phase 显示空状态；无 `file_changes.jsonl` 的 Run 不显示该区域或显示禁用状态，不报错。文件变化区域有独立滚动，不影响 Phase 图和 Calls/Events 布局。

### Loops 工作台

1. 左栏常驻展示所有可发现 Loop。
2. 右侧是 Loop 文件夹的只读结构化预览，不是静态营销详情页。
3. loop.md 以 Markdown 渲染；workflow.py 和其他文本文件以只读代码视图展示；Agents 以列表和定义详情展示。
4. 首版不提供浏览器内文件修改，不允许预览 Loop 根目录之外的文件。

### Backends 工作台

1. 使用列表或表格展示真实可观测的后端状态，不使用装饰性健康分数。
2. 选择 Backend 后展示能力、版本、路径及最近诊断日志。
3. 状态由文字或图标与颜色共同表达，不得只依赖颜色。

### 响应式与可访问性

1. 1440px 桌面同时展示主列表、主工作区和 Inspector；1024px 可将 Inspector 收入抽屉；小于 768px 一次展示一个主区域。
2. 所有图标按钮有 accessible name 和 tooltip；键盘可完成列表选择、Tab 切换和主要 Run 操作。
3. 任何支持动态内容的面板必须有稳定尺寸和独立滚动区域，文本、图节点和控件不得重叠。

### Web API 边界

详细字段在 Web 接口定义中冻结；Spec 要求的接口能力与错误语义如下：

| 能力 | 输入 | 成功输出 | 主要错误 |
|------|------|----------|----------|
| 查询 Loops / Loop 文件 | 可选筛选；loop 名和相对路径 | Loop 摘要列表；受限文件内容 | 404 loop/file 不存在；403 路径越界；422 文件不可预览 |
| 查询 Runs / Run 详情 | 可选状态、Loop、搜索和 cursor；run_id | 分页 Run 摘要；Run/Phase/Call 读模型 | 404 run 不存在；422 筛选无效 |
| 订阅 Run 事件 | run_id、last_event_id、last_file_changes_id | SSE 多 topic 事件（run_event + file_changes）及 per-topic 重连游标 | 404 run 不存在；410 游标已不可恢复 |
| 启动 / 重跑 Run | loop、args、运行选项；重跑时含源 run_id | 新 Run 摘要和 Location | 404 loop/run 不存在；409 状态冲突；422 参数无效 |
| 停止 / 恢复 Run | run_id；恢复 mode=retry/continue | 更新后的 Run 摘要 | 404 run 不存在；409 状态冲突、重放分歧或 continue 不支持 |
| 查询 / 回答 Intervention | run_id、request_id、JSON response | 请求详情；回答后 running Run 摘要 | 404 请求不存在；409 已回答或状态冲突；422 schema 不匹配 |
| 修复 stale Run | run_id | status=failed 的 Run 摘要 | 404 run 不存在；409 Run 非 stale 或进程重新可用；500 原子写失败 |
| 查询 / 诊断 Backends | 可选 backend 名 | Backend 摘要、能力和诊断日志 | 404 backend 不存在；503 诊断进程不可启动 |

---

# 约束

## 七、非功能指标

| 维度 | 指标 | 目标值 |
|------|------|--------|
| 性能 | CLI 启动到开始执行 | < 1s |
| 兼容性 | Python 版本 | 3.10+ |
| 兼容性 | 操作系统 | macOS / Linux |
| 可靠性 | Recover 缓存命中准确性 | 100%（call_id、input_digest 和 succeeded 提交标记同时匹配才返回结果） |
| 可维护性 | 外部依赖 | 运行时：pyyaml, click, rich；开发：pytest；管理：uv |
| 性能 | Runs 首屏 | 在 CI 基准 fixture（1000 Runs，每个 run.json 2KB，所选 Run 1000 条 1KB 事件）上，服务已启动且 OS 文件缓存预热后，API p95 < 500ms；测量 30 次 |
| 实时性 | 已落盘事件到 SSE 可读 | 在单客户端、1KB 事件、无后端执行负载的 CI 测试中，p95 < 500ms；连续测量 100 条 |
| 可靠性 | 事件流断线恢复 | 从最后 event_id 恢复，不丢失已持久化事件 |
| 安全性 | 默认网络暴露 | 仅绑定 127.0.0.1；文件读取限制在 Loop/Run 允许根目录 |
| 兼容性 | 历史 Run | legacy/unversioned JSONL 可显示原始时间线；关联不确定的事件标记 unattributed，不要求迁移原文件 |
| 可访问性 | 键盘与状态表达 | 核心监控和 run/stop/recover/respond 可键盘完成；状态不只依赖颜色 |

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
| Loop | 一个文件夹，包含 loop.md + workflow.py + agents/，定义了一个 Agent 循环工作流 |
| loop.md | Loop 的声明式定义文件，frontmatter 给机器读，body 给 Agent 和人类读 |
| Run | Loop 的一次执行实例，有唯一 uuid，状态持久化到 `runs/lf_<pwd>/<uuid>/` |
| Dispatch | 扫描队列、按优先级取任务、加资源锁、执行 loop 的调度过程 |
| Queue | `~/.loopflow/queue/` 下的 JSON 文件，每个文件是一个待执行任务 |
| Resource Lock | 文件锁，防止同一资源（如 repo）被多个 loop 同时操作 |
| Agent | 一个 Markdown 文件定义的 AI Agent，有名称、能力声明、系统提示词 |
| Agent Call | workflow.py 中一次逻辑 `agent()` 调用，具有稳定 call_id、input_digest 和对应 `<call-id>.jsonl` 缓存 |
| Recover | failed/cancelled Run 的恢复机制：从头重放 workflow，校验并返回前序成功 Call，在目标失败/取消边界执行 retry、continue 或重放到 pending intervention |
| Retry | 为目标失败/取消 Call 创建新 backend session 重新执行；框架默认恢复路径，不单独作为能力字段建模 |
| Continue | 使用目标失败/取消 Call 的 durable session_id 恢复 backend 上下文；原子/隔离 worker 取消边界禁止 continue |
| Intervention | workflow 或 Agent 发出的结构化人工输入请求；持久化后 Run 等待回答且不保留 worker |
| Backend | Agent 后端的抽象层，适配不同的 CLI Agent（kimi/claude/codex 等） |
| Transport | 与 Backend 通信的方式：CLI（子进程）或 ACP（Agent Communication Protocol） |
