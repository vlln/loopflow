---
title: loopflow Spec
description: loopflow 核心功能规格：Agent 循环编排、可校验恢复、人工介入、本地 WebUI、ACP 可选传输、Agent waiting_input 控制协议与运行时追加 prompt（0.27.0）。
type: spec
status: proposed
version: 19
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
| US-017 | 开发者 | 查看 Run 的 Agent 实例图、顺序、分支和并行汇合 | 理解工作流当前进度及历史执行路径 | P0 |
| US-018 | 开发者 | 选择一次 Agent Call 并查看其事件与文件变化 | 以稳定 call_id 定位该次执行的行为与结果 | P0 |
| US-019 | 开发者 | 实时查看所选 Agent Call 的运行过程 | 观察消息、工具调用、重试、错误和最终输出 | P0 |
| US-020 | 开发者 | 在 Loops 工作区浏览 Loop 声明和目录内容 | 无需离开控制台即可检查 loop.md、workflow.py 和 Agents | P1 |
| US-021 | 开发者 | 在 Backends 工作区检查当前环境的后端可用性和诊断日志 | 在运行 Loop 前发现安装、版本或配置问题 | P1 |
| US-022 | 开发者 | 从 WebUI 启动、停止和恢复 Run | 用图形界面完成核心运行管理操作 | P1 |
| US-023 | 开发者 | workflow 阻塞时查看并回答结构化问题 | 不依赖常驻进程介入运行，并在回答后继续同一 Run | P0 |
| US-024 | 开发者 | 明确选择失败 Agent 的 retry 或 continue 恢复方式 | 根据任务副作用和上下文价值控制恢复行为 | P0 |
| US-025 | 开发者 | 在 workflow 或 Agent 定义变化时阻止错误缓存命中 | 避免把旧调用结果或 session 注入语义不同的新调用 | P0 |
| US-026 | 开发者 | 创建 Run 时显式指定工作目录 | WebUI 常驻 server 下让不同 run 在各自项目目录执行和观察，互不污染 | P0 |
| US-027 | 开发者 | 在 WebUI 查看 run 工作目录内的文本、图片和 PDF | 不离开控制台即可检查 agent 新建或修改的常见产物 | P1 |
| US-028 | 开发者 | 创建 Run 时按 loop 声明预填 Arguments 键和默认值 | 不用记忆每个 loop 的参数字面量，降低输入错误 | P1 |
| US-029 | 开发者 | 在白天和夜晚主题间切换 WebUI 外观 | 在不同光照环境下舒适使用 | P2 |
| US-030 | 开发者 | agent 调用失败按类别（auth/quota、transient、task）区别处理 | auth/quota 立即失败不浪费重试，transient 自动退避重试并可续接 session，task 失败快速暴露给 workflow | P0 |
| US-031 | 开发者 | loop 连续失败达到阈值时自动暂停调度 | 无人值守时防止故障 loop 反复消耗配额，恢复后手动解除暂停 | P1 |
| US-032 | 开发者 | run 失联后先进入宽限期再判定失败 | 笔记本睡眠等场景不被误判失败，宽限期内进程恢复则自然调和 | P1 |
| US-033 | 开发者 | 队列任务具有显式状态（pending/deferred/superseded） | 条件不满足挂起、被新任务取代都不计为失败，调度行为可观测 | P1 |
| US-034 | 开发者 | 用 `--transport acp` 选 ACP 后端运行 loop | 用原生 ACP 后端（pi-acp 等）跑 loopflow，ACP 路径可选可用，CLI 仍为默认 | P1 |
| US-035 | 评测 harness / 开发者 | 通过 `loop run --agent` 单独运行 loop 中某个 agent_def | component 级评测和单 agent 调试无需执行完整 workflow | P0 |
| US-036 | 开发者 | CLI 前台 run 进入 waiting_input 时在终端内联回答问题；也可用 `loop respond` 应答既有等待 | 不离开终端完成人工门，消除"run 卡死"误解 | P1 |
| US-037 | 开发者 | 以 `--unattended` 运行 headless 任务，并为 `intervene()` 声明 default/timeout | CI/benchmark 无人值守时不空等：有兜底继续，无兜底明确失败 | P0 |
| US-038 | 开发者 | 让 Agent 在缺少必要信息时通过可发现的结构化协议请求人工输入 | Agent 不靠猜测或自然语言约定即可暂停，并在原 session 收到回答后继续 | P0 |
| US-039 | 开发者 | 在启动 Run 时追加一段临时指令到每次 Agent 调用 | 调试或临时约束无需修改 loop、workflow 或 Agent 定义 | P1 |

---

## 三、模块划分

| 模块 | 提供的能力 | 拥有的数据实体 | 目录路径 | 优先级 |
|------|-----------|----------------|---------|---------|
| CLI | run / recover / respond / status / list / stop 命令解析和路由 | 无 | `src/loopflow/presentation/cli.py` | P0 |
| Workflow Runtime | 加载 workflow.py，提供 agent/parallel/pipeline/intervene/log/args/workflow API，支持 goal 和重放 | Call Cache、Run Event | `src/loopflow/runtime.py`、`src/loopflow/application/runner.py` | P0 |
| Agent | 能力声明（skills/schema/goal/model）marshalling 和 Agent 调用抽象 | 无 | `src/loopflow/agent.py` | P0 |
| Backend Layer | 适配 AI Agent 后端并归一化输出事件 | Backend Session（外部） | `src/loopflow/backends/` | P0 |
| Lock | session、Run 和资源互斥 | Resource Lock | `src/loopflow/lock.py` | P0 |
| Loop Discovery | 扫描已安装 Loop，读取 loop.md 元数据 | Loop Definition | `src/loopflow/discovery.py` | P0 |
| Dispatch | 扫描队列、排序、资源锁检查、执行 Run | 无 | `src/loopflow/dispatch.py` | P1 |
| Queue | 队列读写与状态投影 | Queue Entry | `src/loopflow/queue.py` | P1 |
| Web Application | Loop、Run、AgentGraph、Call、Intervention、Backend 查询模型和应用命令 | Run、Run Index、Intervention | `src/loopflow/application/`、`src/loopflow/infrastructure/web_storage.py` | P0 |
| Web API | 本机 HTTP 查询、命令接口和 Run 事件流 | 无 | `src/loopflow/presentation/web/` | P0 |
| Web Frontend | Runs、Loops、Backends 主从工作区 | 浏览器展示状态（非持久化） | `web/` | P0 |
| File Observation | Call 完成边界快照 diff，以 call_id/label 记录变化 | File Change | `src/loopflow/infrastructure/file_observation.py` | P2 |
| Loop State | per-loop 熔断状态持久化与查询 | Loop State | `src/loopflow/infrastructure/loop_state.py` | P1 |
| ACP Transport | 官方 ACP SDK 管道、permission 和 notification 映射 | 无 | `src/loopflow/infrastructure/transports/acp_sdk.py` | P1 |

依赖方向固定为 Presentation（CLI/Web API/Web Frontend）→ Application（Runner/Web Application/Dispatch）→ Runtime/Agent → Backend/Infrastructure。Discovery、Queue、Lock、File Observation、Loop State 和持久化 Repository 是 Application 使用的基础设施端口实现，不反向依赖 Presentation；Web Frontend 只依赖 Web API 契约。该方向无环，持久化实体只由上表单一模块拥有。

---

# 详细设计

## 四、数据模型

### 文件系统布局

```
pwd (工作目录)                          ~/.loopflow/ (loopflow 数据目录)
├── .agents/                           ├── runs/
│   └── worktrees/                     │   ├── runs_index.jsonl
│       └── lf_<uuid>_<seq>/           │   └── lf_<group-path>/
│           (worktree 隔离，BR-011)     │       └── <uuid>/
│                                      │           (运行实例，见下文)
│                                      └── loops/
│                                          ├── .<name>/    (可下载/可恢复)
│                                          └── <name>/     (分发用声明)
```

`pwd` 是 CLI 创建 Run 时的当前工作目录，`loopflow run` 缺省在此目录执行 workflow。worktree 隔离在 `pwd/.agents/worktrees/` 下创建，属于项目级资源。`~/.loopflow/runs/` 存储 loopflow 内部运行时状态（类比实例化内存数据），`~/.loopflow/loops/` 存储 workflow 定义。runs 按创建时即可确定的 storage group path 分组，映射固定为：CLI 无论省略、传 `--work-dir ""` 还是传非空显式路径，group 均为创建时 cwd；Web/API 缺省时 group 为 server cwd；Web/API 非空显式路径时 group 为该路径。actual working_directory 分别为 CLI 缺省的创建 cwd、两个隔离入口的 `run_dir/work`，或调用者提供的非空显式路径。group 只决定 `lf_<group-path>` 存储位置，不根据最终 actual working_directory 重算。

`runs/runs_index.jsonl` 保存无损定位映射，每个 Run 一行，字段固定为 `working_directory`（真实绝对工作目录）、`runs_directory`（`lf_<group-path>` 分组目录的绝对路径）和 `run_id`。创建 Run 时追加记录；读取旧 Run 或遇到缺失、损坏的索引记录时，允许回退到目录扫描及 `lf_<group-path>` 分组名。

### Loop 定义（文件系统）

```
~/.loopflow/loops/<name>/
├── loop.md                  # 声明式定义（新增）：frontmatter + body
├── workflow.py              # meta = {...}; def run(agent, parallel, pipeline, intervene, log, args, workflow, state)
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
| args | object[] | 否 | Run 参数声明，元素为 `{name, default, description, required}`；name 为非空 string，default 可省略，description 缺省空字符串，required 缺省 false |

**`state` 不属于 loop.md。** workflow 的内部状态（重试计数、阶段标记等）是编排层的实现细节，保持在 `workflow.py` 的 `meta.state` 中。loop.md 声明身份、触发方式、资源需求和创建 Run 所需的参数元数据。loop.md 存在时读取其顶层 `args`；仅在 loop.md 不存在并回退到 `workflow.py meta` 时读取 `meta.args`。

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
| status | string | NOT NULL | pending / deferred / superseded；默认 pending（0.21.0 新增） |
| status_reason | string | optional | deferred/superseded 的原因说明（0.21.0 新增） |
| superseded_by | string | optional | 取代本任务的任务 uuid，仅 status=superseded 时存在（0.21.0 新增） |

### 资源锁（文件系统）

```
~/.loopflow/locks/
└── <resource-type>-<sha256(resource-value)[:16]>.lock
```

锁文件包含 PID 和时间戳。TTL 30 分钟，超时自动清理。

- `.` 前缀的 loop 目录名（如 `.bio-reproducer`）表示可下载/可恢复的 loop，自带完整环境
- 非 `.` 前缀的 loop 目录名（如 `my-workflow`）表示分发用的纯声明 loop，依赖外部环境

### workflow.py meta

`meta` 是 workflow.py 的 legacy 模块级元数据字典；loop.md 不存在时可作为静态发现回退：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| name | string | required | loop 唯一标识 |
| description | string | required | 简短描述 |
| state | object | optional | 声明的持久化状态变量，key 为变量名，value 为默认值。仅支持 JSON 可序列化类型 |
| state.<key> | any | optional | 默认值，类型即约定类型。首次运行时以默认值初始化，每次 agent() 成功后自动持久化 |
| requires | object | optional | workflow 级别的依赖声明 |
| requires.environment | string | optional | 环境声明文件路径（相对路径，如 `environment.yml` 或 `pixi.toml`）。`loopflow run` 启动时校验文件存在，不自动激活或安装。推荐使用 pixi（原生支持 skill 隔离和 npm 依赖），但 loopflow 不约束文件格式 |

`meta` 必须是纯字面量（无变量、函数调用、表达式），用于 legacy 静态发现。`state` 声明持久化变量，运行时通过 `state.key` 属性访问，自动保存到 `state.json`。`requires.environment` 声明环境文件，`loopflow run` 启动时校验存在性，激活由 agent 或用户完成。`meta.phases` 不再是有效字段，不参与运行或 UI 投影。

### 运行实例（文件系统）

```
~/.loopflow/runs/lf_<group-path>/<uuid>/
├── run.json                 # 元数据
├── state.json               # 工作流状态（meta.state 的运行时快照）
├── events.jsonl             # 全部结构化运行事件（按时间序）
├── work/                    # Web/API 缺省或 CLI --work-dir "" 时由框架创建和拥有
├── interventions/           # 原子持久化的人工输入请求与响应
│   └── <request-id>.json
└── <call-id>.jsonl          # 每个 Agent Call 的输出缓存；顶层顺序 ID 与旧 seq 相同
```

`<group-path>` 是上述 storage group path 的绝对路径去掉开头 `/` 后将其余 `/` 替换为 `-`。例如 group path `/Users/vlln/projects/myapp` → `lf_Users-vlln-projects-myapp`。`<uuid>` 是 `uuid.uuid4().hex`，每次 `loopflow run` 生成唯一标识。Web/API 缺省场景先由 server cwd、CLI `--work-dir ""` 场景先由创建时 cwd 算出 group 和 run_dir，再创建最终 working_directory=`run_dir/work`，因此不存在循环定义。

### runs_index.jsonl

```json
{"working_directory":"/Users/vlln/projects/myapp","runs_directory":"/Users/vlln/.loopflow/runs/lf_Users-vlln-projects-myapp","run_id":"<uuid>"}
```

三个字段均为必填字符串。`working_directory` 始终记录 Run 真正执行使用的目录，`runs_directory` 记录按 storage group path 算出的 `lf_*` 目录；Web/API 缺省场景二者刻意不由同一路径推导。索引采用只追加 JSONL；同一 `run_id` 出现多次时以最后一条有效记录为准。`runs_directory` 必须位于当前配置的 runs 根目录内，才能用于 Run 定位。

### run.json

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| loop | string | NOT NULL | loop 定义名称 |
| run_id | string | PK | 唯一运行标识 |
| status | string | NOT NULL | running / waiting_input / cancelling / cancelled / done / failed；stopped 仅 legacy 可读 |
| created | ISO 8601 | NOT NULL | 创建时间 |
| args | object | — | 传入 workflow.py 的参数 |
| working_directory | string | optional | Run 真正执行与文件观察使用的绝对目录；新 Run 必填，legacy Run 可缺失；不用于反推 run_dir 存储分组 |
| counter | integer | NOT NULL | 当前 agent 调用序号 |
| started_at | ISO 8601 | optional | 进程实际开始时间；旧 Run 可缺失 |
| finished_at | ISO 8601 | optional | done / failed / cancelled 的结束时间 |
| updated_at | ISO 8601 | optional | 最近一次元数据更新；用于列表刷新 |
| pid | integer | optional | 当前执行子进程 PID；仅用于进程管理，必须结合进程启动标识校验 |
| process_started_at | ISO 8601 | optional | PID 对应进程的启动时间，用于防止 PID 复用误判 |
| error_summary | string | optional | failed 状态的短错误摘要，不替代完整事件 |
| execution_epoch | integer | NOT NULL | 每次首次执行或恢复递增；worker 写状态时的 fencing token |
| execution_options | object | NOT NULL | 首次执行冻结的有效 backend、model、mock、unattended、append_prompt 等选项；recover 不接受覆盖 |
| cancel_point | string | optional | 最近一次取消点：worker_running / no_worker_running；仅用于派生恢复动作，不表示用户放弃 Run |
| active_call_id | string | optional | 最近一次执行中的 Agent Call；worker_running 取消或 failed 时用于定位 retry/continue 目标 |
| active_worker_atomic | boolean | optional | active worker 是否处于原子提交/隔离边界；true 时 recover_continue 不可用 |
| error_category | string | optional | 失败分类：auth / quota / transient / task / unknown（0.21.0 新增） |
| stale_since | ISO 8601 | optional | 首次判定 stale 的时间，宽限期计时起点；进程恢复或 reconcile 时清除（0.21.0 新增） |

### Intervention

每个请求使用独立 JSON 文件并原子替换，避免服务重启后丢失或读取半写内容：

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| request_id | string | required | Run 内唯一请求 ID |
| source | string | required | workflow / agent |
| key | string | required | workflow 重放路径中稳定且唯一的键 |
| prompt | string | required | 向人类展示的问题 |
| schema | object/null | required | 回答 JSON Schema；null 表示任意 JSON 值 |
| options | string[] | required | 预设回答；可为空 |
| allow_custom | boolean | required | 是否允许 options 之外的非空字符串 |
| request_group_id | string/null | required | 同一次 Agent 控制输出的请求组 ID；workflow 请求为 null |
| request_index | integer | required | 请求在所属组内的零基序号；workflow 单请求为 0 |
| call_id | string/null | required | 关联 Agent Call；workflow 直接请求时为 null |
| session_id | string/null | required | 可继续的 backend session |
| resume_mode | string | required | replay（workflow 请求）/ continue（Agent 请求） |
| status | string | required | pending / answered / closed；stop waiting_input 不关闭 pending request，closed 仅用于显式废弃或 legacy 读取 |
| response | any | optional | immutable 回答，仅 status=answered 时存在；source=agent 时必须是非空 string，source=workflow 时按 schema 可为任意 JSON |
| created_at | ISO 8601 | required | 请求创建时间 |
| responded_at | ISO 8601/null | required | 回答时间 |
| timeout_seconds | number/null | required | 超时秒数；null 表示无超时。仅在 workflow `intervene()` 声明 timeout 时非空 |
| response_source | string | optional | 回答来源：`human`（人工应答）/ `default`（无人值守兜底）/ `timeout_default`（惰性超时兜底）；仅 status=answered 时存在，旧记录缺省视为 `human` |

旧 Intervention 文件允许缺少 vNext 字段：`source` 按 `resume_mode=continue` 推导为 agent，否则为 workflow；`options` 缺省 `[]`；`allow_custom` 在 options 非空时缺省 true，在 legacy boolean schema 时推导为 false，其余缺省 true。旧 Agent request 缺少 `request_group_id/request_index` 时，以 `(call_id, session_id)` 派生 group，并按 `(created_at, request_id)` 确定稳定顺序，同时将该次恢复标记为 unverified；workflow 请求的 group 为 null、index 为 0。读取兼容不改写原文件；新写入文件必须包含这些字段。

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

当 Agent waiting_input 控制协议可用时，框架控制对象与业务 `output` 是互斥分支：正常完成必须匹配业务 schema；请求输入必须匹配框架 waiting_input schema，且不要求填充业务必填字段。`__loopflow` 是框架保留字段，业务 schema 不得声明。框架控制对象只驱动 Run 生命周期，不作为业务结果返回 workflow。

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
| `agent_start` | agent 调用开始（含 call_id、input_digest、label、agent_def） | loopflow 特有 |
| `agent_session` | backend session ID 首次可用（含 call_id、session_id） | loopflow 特有 |
| `agent_thought_chunk` | agent 思考过程 | ACP `agent_thought_chunk` |
| `agent_message_chunk` | agent 文本输出（实时追加，流式 chunk） | ACP `agent_message_chunk` |
| `tool_call` | 工具调用开始 | ACP `tool_call_start` |
| `tool_call_update` | 工具调用进度/完成 | ACP `tool_call_progress` |
| `usage_update` | token 用量 | ACP `usage_update` |
| `agent_done` | agent 调用完成（含 call_id、status、session_id、exit_code、duration_ms） | loopflow 特有 |
| `agent_error` | agent 调用失败 | loopflow 特有 |

新写入缓存以 `call_id` 标识逻辑调用，以 `input_digest` 校验规范化调用输入。digest 覆盖 workflow.py 内容摘要、最终 user/system prompt、输出 schema、backend、model、Agent 定义和影响调用语义的执行选项。密钥和环境变量值不得写入 digest 原文或缓存。

`<call-id>.jsonl` 缓存文件在 agent 执行期间**实时追加**事件，获得 backend session ID 时立即追加 `agent_session`，完成后写入 `agent_done`。恢复缓存命中要求 call_id 和 input_digest 均匹配，且存在 `agent_done(status=succeeded, exit_code=0)`；否则不得返回成功缓存。旧缓存缺少新字段时只允许 unverified legacy retry。

同一 Call 的 retry 以新的 `agent_start` 开始生命周期段，continue 以 `agent_resume` 开始。缓存 reader 只在一个段内匹配 digest、提取消息和完成标记，不跨段拼接失败输出。

`parallel()` 和 `pipeline()` 在启动线程前按输入位置预分配稳定 call_id，线程完成顺序不得影响逻辑身份。

CLI 后端将其原生输出转换为 ACP 兼容事件后写入缓存。未来 ACP 后端直接透传 `SessionNotification`。

### events.jsonl

所有事件按时间顺序追加写入，用于 UI 重建 Agent 实例图和调试。新写入 `events.jsonl` 的事件使用统一信封；运行时将缓存/后端事件写入 `events.jsonl` 时完成信封转换。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| version | integer | required | 事件 schema 版本 |
| event_id | integer | required | Run 内严格递增的事件序号 |
| type | string | required | 事件类型 |
| ts | ISO 8601 | required | 事件产生时间 |
| run_id | string | required | 所属 Run |
| call_id | string | optional | 所属 Agent Call 的稳定标识；Agent 事件必填 |
| payload | object | required | 事件类型专属数据 |

每个 `agent_start` 的 `call_id` 对应 AgentGraph 中唯一节点；payload 的 `label` 是显示名，`agent_def` 标识定义来源。顺序调用生成 sequential edge；`parallel()` 生成 fork/join edge。用户选择节点后仅展示该 call_id 关联的事件和文件变化，不按 label 合并重复调用。

新事件示例：

```jsonl
{"version":2,"event_id":1,"type":"agent_start","ts":"2026-07-18T20:00:01Z","run_id":"abc","call_id":"call-1","payload":{"label":"采集","agent_def":"collector","session":"wf_abc_1"}}
{"version":2,"event_id":2,"type":"agent_message_chunk","ts":"2026-07-18T20:00:02Z","run_id":"abc","call_id":"call-1","payload":{"content":"开始处理..."}}
{"version":2,"event_id":3,"type":"agent_done","ts":"2026-07-18T20:00:03Z","run_id":"abc","call_id":"call-1","payload":{"exit_code":0,"duration_ms":2000}}
```

事件分类按以下顺序判定，分类互斥：无法解析的完整 JSONL 行或解析后不是 object，进入 `malformed`；object 缺少 `version` 字段时视为 `legacy`；存在 `version` 但值不是 integer `2` 时进入 `malformed`；`version=2` 时再校验必填信封字段，Agent 关联事件还必须有非空 string `call_id`，不合约者进入 `malformed`。Agent 关联事件可机械判定为 `type` 以 `agent_` 开头，或 `type` 属于 `tool_call`、`tool_call_update`、`usage_update`、`message`、`retry`；其他事件类型不因缺少 call_id 单独判为 malformed。Legacy reader 保证原始事件时间线可读；只有具备明确 call_id 或其他稳定证据时才建立 Call 关联。并行交错或证据不足的结构合法 legacy 事件标记为 `unattributed`，不得按文件位置或最近事件虚构归属。legacy phase 事件可在原始时间线显示，但不恢复为当前 AgentGraph 节点。

RunDetail 事件投影同时公开 `unattributed`、`malformed` 数组及对应 count，count 必须等于对应数组长度。`unattributed` 元素是保持原字段的 legacy event object。`malformed` 元素固定为 `{reason, raw}`：`reason` 是 `invalid_json`、`non_object`、`unsupported_version`、`invalid_envelope` 或 `missing_call_id`；`raw` 对可解析行保留原 JSON 值，对 `invalid_json` 保留 UTF-8 replacement 解码后的原始行。Malformed 事件不进入 AgentGraph、Call、合法事件数组或 unattributed；同文件中的其他合法事件仍继续投影。

### file_changes.jsonl

工作目录文件变化观察数据，按 Agent Call 完成边界快照 diff 采集。与 `events.jsonl` 严格分离——不参与业务事件流、不参与确定性重放。通过 SSE `file_changes` topic 实时推送；关联语义以 ADR-0052 为准，传输语义见 [ADR-0041](../adr/0041-sse-multi-topic-transport.md)。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| seq | integer | required | Run 内从 1 开始严格递增的序号，作为 SSE `file_changes` topic 的游标（详见 [ADR-0041](../adr/0041-sse-multi-topic-transport.md)） |
| call_id | string | required | 产生这些变化的 Agent Call，与 events.jsonl 的 call_id 一致 |
| label | string | required | 该 Agent Call 的显示标签；不作为关联主键 |
| ts | ISO 8601 | required | 快照拍摄时间 |
| changes | object[] | required | 文件变化列表 |
| changes[].path | string | required | 相对 pwd 的文件路径 |
| changes[].action | string | required | `created` / `modified` / `deleted` |
| changes[].size | integer | created/modified 时必填 | 变化后的文件大小（bytes） |
| changes[].prev_size | integer | modified/deleted 时必填 | 变化前的文件大小（bytes） |

采集时机：Run 启动时建立基线快照；每次 Agent Call 完成后对 pwd 拍摄快照，与上一快照 diff，并将变化归属到该 call_id。无变化不追加记录。goal 内部迭代完成后的观察仍归属同一逻辑 Call。

扫描范围：pwd 下所有文件，排除 `.agents/worktrees/`、`.git/`、`__pycache__/`、`.pyc`。`meta.file_observation.exclude` 可声明额外排除路径（glob 模式）。`meta.file_observation.enabled` 设为 `false` 可禁用观察（默认 `true`）。

无 `file_changes.jsonl` 的 Run（legacy 或禁用）在 WebUI 显示空状态，不报错。

### Loop 状态（文件系统，0.21.0 新增）

```
~/.loopflow/loop_state/
└── <loop-name>.json          # 每个 loop 一个熔断状态文件
```

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| consecutive_failures | integer | NOT NULL | 连续失败 run 数；该 loop 任一 run 进入 done 时归零 |
| paused | boolean | NOT NULL | 熔断暂停标记；true 时 dispatch 不消费该 loop 的队列任务 |
| paused_reason | string | optional | 暂停原因（如 `failure_streak:5`） |
| paused_at | ISO 8601 | optional | 暂停时间 |
| last_run_id | string | optional | 最近一次计入 streak 的 run |

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
| BR-007 | workflow.py 的 legacy `meta` 必须是纯字面量 | loop.md 不存在而走静态发现回退时 | 只提取允许的元数据字段，不执行表达式；不读取 `meta.phases`，不用于 AgentGraph 拓扑 |
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
| BR-025 | AgentGraph、state、Run status 分层展示 | 构建 Run 读模型 | AgentGraph 表示 Call 执行拓扑；state 表示 `state.json` 当前投影；Run status 表示 running/waiting_input/cancelling/cancelled/done/failed，三者不得混用 |
| BR-026 | Agent Call 详情只展示有证据的数据 | 用户选择 AgentGraph 节点 | 节点、Call、events 和 file changes 只通过稳定 call_id 关联；label 仅展示，不合并同名调用，不从日志位置或文案推断归属 |
| BR-027 | Run 操作受状态和恢复边界约束 | WebUI 请求 run/stop/recover/respond/reconcile | running 允许 stop；waiting_input 允许 respond 或 stop；failed 允许 recover；cancelled 在存在可重放边界时允许 recover，在存在 pending intervention 时允许 respond；done/legacy stopped 不允许 recover；stale 只允许 reconcile；rerun 是创建新 Run 的便利动作，不作为旧 Run 状态转换；非法转换返回冲突错误且不修改文件 |
| BR-028 | Loop 文件预览限制在 Loop 根目录 | WebUI 请求 Loop 文件 | 解析后的真实路径必须位于所选 Loop 根目录内；拒绝路径穿越、符号链接逃逸和任意绝对路径 |
| BR-029 | Run 事件流可断线恢复 | WebUI 订阅 Run | 客户端按 event_id 请求断点后的事件；服务端可重放已持久化事件并继续推送新增事件，重复连接不得重复执行 Run |
| BR-030 | Backend 诊断基于真实能力 | WebUI 查询后端 | 仅展示 BackendManager 或诊断命令可观测的安装、版本、能力、transport 和日志；不得伪造 VRAM、延迟或健康分数 |
| BR-031 | Run 与 state 文件原子更新 | 创建 Run、状态变化、state 持久化或进程退出 | `run.json` 和 `state.json` 各自在同目录写临时文件，flush 后独立原子替换，不承诺跨文件事务；仅替换 run.json 时在同一份新 JSON 中更新其 updated_at，state.json 不增加保留字段 |
| BR-032 | 陈旧 running 状态可识别和修复 | 读取或 reconcile status=running 的 Run | 读取时同时校验 pid 和 process_started_at；首次确认进程不存在或身份不匹配时原子记录 stale_since，读模型返回 stale；后续读取不重复改写。显式 reconcile 再次校验，满足 BR-052 宽限期后原子写 status=failed、finished_at、updated_at 和 error_summary，清除 pid/process_started_at/stale_since，随后允许 recover |
| BR-033 | 恢复模式显式选择 | failed/cancelled Run 执行 recover | retry/replay 是默认恢复路径，创建新 session 或重放到 pending 边界；continue 使用原 session_id；缺少 durable session 能力、目标 Call 未落盘 session_id 或 active worker 为原子/隔离边界时返回 continue_not_supported，不静默降级 |
| BR-034 | stop 取消当前 execution attempt | running/waiting_input Run 执行 stop | 先持久化取消意图，再终止已验证身份的进程组；SIGTERM 超时后 SIGKILL；最终 cancelled；cancelled 表示本次 execution epoch 被取消，不表示 Run identity 不可恢复 |
| BR-035 | 人工介入可持久化重放 | workflow 调用 intervene 或 Agent 返回结构化 requests | 创建 request 后 Run 进入 waiting_input 且 worker 退出；workflow `intervene()` 是 routing/control gate，通过 replay 返回回答给 workflow；Agent requests 是继续执行所需输入，仅在 durable session 已落盘时创建并通过 continue 返回给 Agent；waiting_input 被 stop 后 pending request 保留，respond 可恢复同一 Run |
| BR-036 | Intervention 不从自然语言推断 | Agent 输出问题文本 | 仅结构化 `__loopflow.status=waiting_input` 且含 requests 的 control output 触发 waiting_input；普通文本按 Agent 结果处理 |
| BR-037 | Intervention 批量回答只提交一次 | pending intervention 接收 responses | Run 当前全部 pending requests 必须在一个 batch 中回答；先校验 request 集合完整、request_id 唯一、均未回答且每个 response 满足 options/custom，再全有或全无地写为 answered，并只启动一次恢复。缺少任一 pending request、任一校验失败或后续重复提交均不写入任何回答，分别返回 validation_failed / intervention_already_answered，不覆盖 response 或部分恢复。单 request 也使用同一 batch 语义 |
| BR-038 | 首次执行冻结恢复选项 | 创建 Run | 将自动选择后的有效 backend/model 和其他执行选项写入 run.json；recover 沿用且不接受覆盖 |
| BR-039 | CLI resume 是 deprecated recover retry 别名 | failed/cancelled Run 调用旧 CLI resume | 执行 recover --mode retry 并输出弃用提示；Web API 不保留 resume 端点；legacy stopped 仍拒绝 |
| BR-040 | Workflow 满足确定性重放契约 | 首次执行和 recover | Call 路径只能稳定依赖 args、缓存 Agent 结果、Intervention 回答和确定性 Python；时间、随机数、变化的环境或实时外部读取不得直接决定路径 |
| BR-041 | Recover 必须到达全部目标 | workflow 重放 | 到达任一预期失败 Call/Intervention 前出现不同 Call、digest 不同或提前结束，或 execution 结束时仍有未到达的恢复目标，均报 replay_diverged，不得标记 done。并行 Agent intervention 可携带多个 continue target，按 call_id 分别验证和恢复，不得只恢复第一个 target |
| BR-042 | AgentGraph 从运行证据涌现 | Run 创建及 Agent 事件到达 | 空 Run 的 AgentGraph 为空；每个首次出现的 call_id 创建唯一节点，顺序、fork、join edge 仅由结构化运行事件生成；不读取 `meta.phases` 或预造占位节点；详见 ADR-0052 |
| BR-043 | 工作目录文件变化观察 | Agent Call 完成且 `meta.file_observation.enabled` 非 false | 对 run 的工作目录（BR-044）拍摄快照并与上一快照 diff，以 call_id/label 追加到 `file_changes.jsonl`（含 `seq`）；不写入 events.jsonl、不参与重放；通过 SSE `file_changes` topic 推送（ADR-0041）；关联语义以 ADR-0052 为准 |
| BR-044 | Run 显式工作目录 | CLI 或 Web/API 创建 Run | 非空显式路径必须是已存在目录的绝对路径；CLI 校验失败时非零退出，Web/API 返回 422 `validation_failed`。executor 子进程 chdir 到 actual working_directory 执行 workflow 与文件观察。CLI 缺省为创建 cwd；CLI `--work-dir ""` 以创建 cwd 分组后创建 `run_dir/work`；CLI 非空显式路径仍以创建 cwd 分组、actual 为该路径。Web/API 缺省以 server cwd 分组后创建 `run_dir/work`（ADR-0054）；Web/API 非空显式路径以该路径分组且 actual 同路径。actual 写入 run.json 和 runs_index，group 不据此重算；recover/rerun 沿用；详见 [ADR-0042](../adr/0042-run-working-directory.md) |
| BR-045 | 文件观察基线快照 | Run 启动时且观察启用 | 先建立基线快照（内存态，不产生记录），每个 Agent Call 完成后的 diff 针对基线或上一快照；`created` 仅表示相邻观察边界间新建，预先存在的文件首改标记 `modified`；关联与基线语义以 ADR-0052 为准 |
| BR-046 | Run/Loop 文件预览 | WebUI 点击文件 / 文件预览 API | 仅限所属工作目录或 Loop 根目录内的相对 POSIX 路径，resolve 越界拒绝（403 `path_forbidden`）；文本以内联 JSON 返回，上限 1 MiB；png/jpg/jpeg/gif/svg/webp/bmp/ico/pdf 通过 raw 端点只读返回，上限 50 MiB；其他二进制或超限文件返回 422 `file_not_previewable`；resolve/size 校验通过后读取仍发生 OSError 时返回 500 `file_read_failed`，不得发送部分 bytes |
| BR-047 | Loop args 声明预填 | loop.md 顶层 `args` 声明 `[{name, default, description, required}]` 时 | Loop summary/detail API 返回 `declared_args`（非法声明静默忽略）；New Run 对话框在首次打开及切换 Loop 时按所选 Loop 声明重建键值行（default 填入，required 仅提示）；无声明时为空白起始。仅在 loop.md 不存在的 legacy 回退路径读取 `workflow.py meta.args`。该 active 契约是 BL-054 的权威依据，本轮不新增第二套参数声明 |
| BR-048 | WebUI 主题 | 用户点击 rail 主题切换按钮 | 日夜主题切换（CSS 变量调色板）；选择持久化于 localStorage；未选择时跟随系统 `prefers-color-scheme` |
| BR-049 | Agent 失败按类别处理 | `agent()` 后端调用失败 | 失败分类为 auth/quota/transient/task/unknown，来源优先级：后端结构化上报 > stderr 模式匹配。transient 按既有退避（3/9/27s）自动重试且 recover 可 continue；auth/quota 与 task 不自动重试，直接持久化失败。分类写入 agent_done 事件与 run.json `error_category` |
| BR-050 | Loop 失败熔断 | run 进入 failed 终态 | 该 loop 的 `consecutive_failures` +1（done 时归零）；达到阈值（默认 5，loop.md frontmatter 可用 `failure_threshold` 覆盖）时置 `paused=true` 并写 `paused_reason`。paused 的 loop 其队列任务在 dispatch 中标记 deferred 留队，不计失败 |
| BR-051 | 熔断解除手动显式 | 用户执行 loop 恢复操作（CLI/Web） | 清除 `paused` 与 `consecutive_failures`；不提供自动解除 |
| BR-052 | stale 宽限期 | 读模型判定 stale / 显式 reconcile | 首次判定 stale 时记录 `stale_since`；宽限期（默认 24h）内 reconcile 返回 409 `run_in_grace`，宽限期满后按 BR-032 执行。宽限期内 worker 进程恢复并写入终态时以 worker 写入为准，清除 `stale_since`（对 BR-032 的补充约束） |
| BR-053 | 队列任务显式状态 | enqueue / dispatch | 任务状态机 pending/deferred/superseded。资源锁不可得时任务标记 deferred 留队（BR-019 语义不变，仅显式化）；`enqueue --supersede` 将同 loop 的 pending/deferred 任务标记 superseded 并记录 `superseded_by`；deferred/superseded 不计入 dispatch errors。loopflow 无常驻调度器，misfire 补偿暂不适用 |
| BR-054 | ACP 传输可选 | `loopflow run`/`enqueue` 携带 `--transport acp` | 路由到 ACP 后端（AcpSdkBackend）；默认 CLI 不变。ACP 路径加载可选依赖 agent-client-protocol，缺失时报错提示安装 extra |
| BR-055 | ACP permission auto-approve | ACP 后端发 `request_permission` | fire-and-forget 模型下统一 auto-approve-all（对应 acpx approve-all，不做读写分级），消除 ADR-0018 的授权死锁 |
| BR-056 | ACP notification 全量映射 | ACP 后端 `session/update` | `agent_message_chunk`→agent_message、`agent_thought_chunk`→thought、`tool_call_*`（信息性，不要求 client 响应）、`usage_update` 全映射到 loopflow 事件，补齐 ADR-0021 的 stub |
| BR-057 | ACP 上的 continue | failed/cancelled Run 用 `--mode continue` 恢复且后端声明 `loadSession`/`resume` | 声明能力的 ACP 后端可 continue（session/load 续接）；不声明则 continue_not_supported，best-effort（与 BL-001 能力门控一致） |
| BR-058 | 单 agent 运行 | `loopflow run <loop> --agent <name>` | 不导入、不执行 workflow.py，workflow digest 为 None；`--prompt`/`--prompt-file` 二选一必填；agent_def 不存在即以明确错误退出，不创建 Run；产出完整 Run（run_dir/run.json/缓存/事件），可 recover；`--args` 在该模式下被拒绝。详见 [ADR-0055](../adr/0055-single-agent-run.md) |
| BR-059 | CLI 前台内联应答 | 前台 `loopflow run`/`loopflow respond` 遇到 pending intervention 且 stdin 为 tty | 逐题内联提问（options 编号选择 / allow_custom 自由文本），校验与 `answer_requests()` 一致；应答后经应用层路径恢复同一 Run，循环直至终态；Ctrl-C 保持 waiting_input 退出且回答不落盘。详见 [ADR-0056](../adr/0056-waiting-input-lifecycle.md) |
| BR-060 | intervene default/timeout | workflow 调用 `intervene(..., default=..., timeout=...)` | default 在调用时通过 options/allow_custom/schema 校验，否则 ValueError；timeout 仅在声明 default 时有效；重放到期（created_at + timeout 已过）的 pending 请求自动以 default 回答（惰性求值）；default/timeout 变更按 replay_diverged 处理；已回答请求记录 response_source |
| BR-061 | 无人值守模式 | `loopflow run --unattended` | 冻结进 Run 执行选项，recover 继承；遇到 intervention 请求：有 default 则以 default 回答并继续（不进入 waiting_input），无 default 则以 `intervention_unattended` 失败；前台 stdin 非 tty 且未声明时不隐式套用，打印应答指引后以 waiting_input 退出 |
| BR-062 | Agent intervention 协议可发现 | Agent 调用使用可续接 backend | 框架在最终 Agent prompt 中注入最小 `__loopflow.status=waiting_input` 协议、适用条件和示例；不从自然语言问题推断请求。动态 transport 必须在组装 prompt 前完成 capability preflight，不能先宣告能力再于回答时拒绝续接 |
| BR-063 | 业务输出与框架控制互斥 | Agent 同时具有业务 output schema 和 intervention 能力 | 有效输出 schema 表达“业务结果或 waiting_input 控制对象”；控制分支不要求业务字段，业务分支不得包含保留字段 `__loopflow`；goal 模式的正常分支继续要求 `__goal`，waiting_input 仍是独立控制分支并优先处理 |
| BR-064 | Agent intervention 仅继续原 session | Agent 返回合法 waiting_input 控制对象 | 仅在 backend 声明 resume_session + durable_session_id 且本次调用已落盘 session_id 时创建 source=agent、resume_mode=continue 的请求；同一控制对象的 requests 共享 request_group_id 并按数组位置写 request_index。回答后按 request_group_id 分组，每组只发送到其记录的 call_id/session_id；并行 Call 的多个组作为多个 continue targets 在同一次 workflow 重放中分别恢复。能力不足时不创建 pending request，以 `agent_intervention_not_supported` 失败并提示改用 workflow `intervene()` 或可续接 backend；不得静默创建新 session 重跑。Agent 不得声明 default/timeout |
| BR-065 | Run 级追加 prompt | CLI `loopflow run --append-prompt TEXT` 或 Web 创建 Run 提供 `append_prompt` | 非空 UTF-8 文本作为不受信任的用户指令，以独立 `<run-append-prompt>` 段追加到本 Run 每次 Agent 调用的动态 prompt；不提升为 system prompt，不修改 Agent 定义。值按 UTF-8 编码上限 64 KiB，空字符串等价于未提供；超限在创建 Run 前以 validation_failed 拒绝且不创建 Run。值冻结进 execution_options，recover 不接受覆盖，并参与每次 Call input_digest；单 agent 入口同样适用 |

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

`status` 固定为 `waiting_input`。`requests` 为非空数组且同一对象内 key 唯一；每个 request 的 `key` 和 `prompt` 为非空字符串，`options` 为 string array，`allow_custom` 为 boolean。response 统一为 string；`allow_custom=false` 时 response 必须属于 options，`allow_custom=true` 时可以是任意非空 string。Agent request 不接受 default/timeout。该控制对象不作为业务结果返回给 workflow；满足 durable session 条件时转为 Intervention，否则以 `agent_intervention_not_supported` 失败。

回答后框架向原 Agent session 发送统一信封，单问题与多问题格式相同：

```json
{
  "__loopflow": {
    "status": "input_received",
    "responses": [
      {"key": "scope", "response": "扩大"}
    ]
  }
}
```

responses 在每个 request_group_id 内按 request_index 恢复原始顺序，只包含稳定 key 和已校验的 string response，不暴露 request 文件中的 digest、路径或内部状态。每个组只发送给其持久化的 call_id/session_id；并行 Agent 同时产生多个组时分别构造信封并恢复对应 session，不把不同 Agent 的回答混入同一信封。

---

## 六、UI 约束

WebUI 是本地开发者控制台，视觉规范以 [`references/DESIGN.md`](../../references/DESIGN.md) 为唯一权威源。本节定义信息架构和行为边界，不重复颜色、字体、圆角和间距 token。

### 一级工作区

| 工作区 | 主列表 | 详情区域 | 核心操作 |
|--------|--------|----------|----------|
| Runs | 常驻 Runs 列表，支持状态、Loop 和文本筛选 | AgentGraph、Call 详情、事件、文件变化和待回答 Intervention | run / stop / recover / respond / rerun |
| Loops | 已发现的 Loop 声明列表 | loop.md 渲染、workflow.py、Agents、允许范围内的文件、关联 Runs | run / enqueue |
| Backends | Backend 列表及可用状态 | capabilities、CLI 路径、版本、transport、诊断日志 | 执行诊断 |

Queue 首版作为 Runs 工作区内的 `Runs / Queue` 模式，不设一级导航；当调度功能扩展后可通过新 Spec 提升为一级工作区。

### Runs 工作台

1. 左栏是常驻 Runs 列表，不使用独立列表页作为进入详情的前置步骤。
2. 中间上方展示 AgentGraph；每个 call_id 是唯一节点，label 为显示名，顺序调用、并行 fork 和汇合 join 必须可区分。图从结构化 Agent 事件涌现，不预造 Phase 节点，也不把同 label 的不同 Call 合并。
3. 中间下方展示所选 Agent Call 的 Events；Run 当前 state 作为 Run 级 Inspector 信息展示，不伪装成 Call state diff。
4. 右栏展示所选 Call 的消息、工具调用、重试、错误、输出和原始事件；没有 call_id 证据的 legacy 事件只进入 unattributed 时间线。
5. 切换 Run 或 Agent Call 时保留列表筛选和布局尺寸；实时事件不得引发布局跳动。
6. failed/cancelled Run 明确提供可用的 Recover/Retry 与 Continue 操作；Continue 不可用时展示后端能力、session 持久化或原子 worker 边界原因，不静默执行 Retry。
7. waiting_input Run 展示结构化 prompt 和匹配 schema 的输入控件；回答只提交一次，提交期间禁用重复操作。
8. 文件变化面板按所选 call_id 高亮该 Agent Call 完成时观察到的 created/modified/deleted；按 SSE `file_changes` topic 实时更新。无变化或无 `file_changes.jsonl` 的 Run 显示空状态，不报错。面板滚动不影响 AgentGraph 和 Events 布局。
9. New Run 对话框提供可选的 Append prompt 多行输入，提交为 `append_prompt`；输入超过 64 KiB 时就地显示校验错误且不发送请求。Arguments 键值编辑器按 BR-047 在首次打开和切换 Loop 时重建预填行。
10. 点击允许预览的图片时显示原始比例受视口约束的图像；PDF 使用只读内嵌查看器；加载中、超限、不支持和读取失败均有明确状态，不把二进制内容解码进文本区域。

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
| 查询 Loops / Loop 文件 | 可选筛选；loop 名和相对路径 | Loop 摘要列表；文本文件内容；图片/PDF raw bytes + 原始 media type | 404 loop/file 不存在；403 路径越界；422 文件不可预览或超过 50 MiB；500 file_read_failed |
| 查询 Runs / Run 详情 / Run 文件 | 可选状态、Loop、搜索和 cursor；run_id 和相对路径 | 分页 Run 摘要；Run/AgentGraph/Call 读模型；文本文件内容；图片/PDF raw bytes + 原始 media type | 404 run/file 不存在；403 路径越界；422 筛选无效、文件不可预览或超过 50 MiB；500 file_read_failed |
| 订阅 Run 事件 | run_id、last_event_id、last_file_changes_id | SSE 多 topic 事件（run_event + file_changes）及 per-topic 重连游标 | 404 run 不存在；410 游标已不可恢复 |
| 启动 / 重跑 Run | loop、args、backend/model/mock、working_directory、可选 `append_prompt`；重跑时含源 run_id | 新 Run 摘要和 Location；append_prompt 冻结进 execution_options | 404 loop/run 不存在；409 状态冲突；422 参数无效或 append_prompt 超过 64 KiB |
| 停止 / 恢复 Run | run_id；恢复 mode=retry/continue | 更新后的 Run 摘要 | 404 run 不存在；409 状态冲突、重放分歧或 continue 不支持 |
| 查询 / 回答 Intervention | run_id；非空 `responses:[{request_id,response}]`，必须覆盖本次全部 pending requests | 请求详情；全部回答原子持久化后只恢复一次，返回 running Run 摘要 | 404 请求不存在；409 已回答或状态冲突；422 集合不完整、重复 request_id 或回答不匹配 |
| 修复 stale Run | run_id | status=failed 的 Run 摘要 | 404 run 不存在；409 Run 非 stale 或进程重新可用；500 原子写失败 |
| 查询 / 诊断 Backends | 可选 backend 名 | Backend 摘要、能力和诊断日志 | 404 backend 不存在；503 诊断进程不可启动 |
| 暂停解除 / 恢复 Loop | loop 名 | 更新后的 Loop 摘要（含 paused 状态） | 404 loop 不存在 |
| 修复 stale Run（宽限期约束） | run_id | 同既有 reconcile | 宽限期内返回 409 `run_in_grace`，其余同既有 |

### 失败与熔断呈现（0.21.0 新增）

- Run 列表与详情呈现 `error_summary` 与失败分类（`error_category`），失败原因不得只能翻事件时间线。
- 熔断呈现分级：streak 首次失败在 Loop 摘要醒目呈现；连续重复失败聚合为一条（streak 计数），不逐条刷屏。
- paused 的 Loop 在 Loops 工作区显示暂停徽标、原因与恢复操作。

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
| 兼容性 | 历史 Run | legacy/unversioned JSONL 可显示原始时间线；关联不确定的事件标记 unattributed；旧 Intervention 缺少 source/options/allow_custom 时按数据模型默认值读取；均不要求迁移原文件 |
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
| agent-client-protocol | 可选（extra `[acp]`） | ACP 协议管道（Pydantic schema + asyncio stdio transport）；仅 --transport acp 时 import，默认 CLI 路径不加载 |
| Python 标准库 | 3.10+ | 所有运行时能力（subprocess/threading/json/pathlib/importlib） |

---

## 九、术语表

| 术语 | 代码标识符 | 定义 |
|------|------------|------|
| Loop | `LoopRepository` / `loop` | 包含 loop.md、workflow.py、agents/ 的 Agent 循环工作流定义 |
| loop.md | `loop.md` | Loop 的声明式定义文件，frontmatter 给机器读，body 给 Agent 和人类读 |
| Run | `run_id` / `RunRepository` | Loop 的一次执行实例；状态持久化到 `runs/lf_<group-path>/<uuid>/`，实际目录由 working_directory 记录 |
| Dispatch | `dispatch` | 扫描队列、排序、加资源锁并执行 Run 的调度过程 |
| Queue | `QueueRepository` / `task_id` | queue 目录中的待执行任务集合 |
| Resource Lock | `FileLock` | 防止同一资源或 session 被并发操作的文件锁 |
| Agent | `Agent` / `agent_def` | Markdown 定义的 AI Agent，包含名称、能力声明和系统提示词 |
| Agent Call | `call_id` | 一次逻辑 agent() 调用，具有稳定 input_digest 和 `<call-id>.jsonl` 缓存 |
| AgentGraph | `agent_graph` | 由 Agent/fork/join 事件投影的 Call 实例有向图；call_id 唯一，label 仅显示 |
| Recover | `recover` / `recovery_mode` | failed/cancelled Run 的确定性重放与目标边界恢复机制 |
| Retry | `retry` | 为目标 Call 创建新 backend session 重新执行的默认恢复路径 |
| Continue | `continue` / `session_id` | 使用 durable session_id 恢复原 backend 上下文 |
| Intervention | `InterventionSummary` / `request_id` | workflow 或 Agent 发出的结构化人工输入请求 |
| Backend | `Backend` / `backend_name` | 适配不同 AI Agent 执行器的抽象层 |
| Transport | `transport` | Backend 通信方式：CLI 子进程或 ACP |
| 失败分类 | `error_category` | auth/quota/transient/task/unknown 分类，决定重试与续接策略 |
| 熔断 | `paused` / `consecutive_failures` | Loop 连续失败达阈值后暂停调度的状态 |
| 宽限期 | `stale_since` | stale Run 从首次判定到允许 reconcile 的时间窗口 |
| Deferred | `status=deferred` | 条件不满足而挂起留队、不计失败的队列状态 |
| Supersede | `status=superseded` | 被新任务显式取代且不计失败的队列状态 |
| ACP Transport | `AcpSdkBackend` / `transport=acp` | 官方 Python ACP SDK 承载的可选传输路径 |
| 单 agent 运行 | `single_agent` / `--agent` | 不执行 workflow.py、直接运行一个 agent_def 的完整 Run 模式 |
| 无人值守 | `unattended` | intervention 有 default 则继续、无 default 则明确失败的 headless 模式 |
