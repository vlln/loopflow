---
name: make-loop
description: >
  Use this skill when creating or modifying a loopflow workflow (loop).
  Encodes the structure, conventions, constraints, and design principles
  of loop definitions — what every loop must have, what it may have, and why.
---

# make-loop

## Loop 是什么

Loop 是 loopflow 的工作流定义。一个 loop 定义了一组按顺序执行的 phase，
每个 phase 由一个 agent 完成。Loop 位于 `~/.loopflow/loops/<name>/`。

## 目录结构

```
~/.loopflow/loops/<name>/
├── pixi.toml              # 环境、依赖、skill 安装
├── workflow.py            # phase 编排逻辑
└── agents/
    ├── _base.md           # 公共约定（抽象 agent，不直接调用）
    ├── <phase1>.md        # Phase 1 agent 定义
    ├── <phase2>.md        # Phase 2 agent 定义
    └── ...
```

## workflow.py

### 必须导出

```python
meta = {
    "name": "my-loop",           # loop 名称
    "description": "...",         # 一句话描述
    "phases": [                   # phase 顺序列表
        {"title": "Phase 1", "detail": "做什么"},
        {"title": "Phase 2", "detail": "做什么"},
    ],
    "state": {                    # 可选，可变的运行时状态
        "attempt": 0,
    },
}


def run(agent, parallel, pipeline, phase, log, args, workflow, state):
    ...
```

### run() 参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `agent(prompt, *, agent_def, **kwargs)` | callable | 调用一个 agent，返回 str 或 dict |
| `parallel(thunks)` | callable | 并行执行多个 thunk |
| `pipeline(items, *stages)` | callable | 流水线处理 |
| `phase(title)` | callable | 标记新 phase 开始 |
| `log(message)` | callable | 输出日志 |
| `args` | dict | 用户传入的参数（CLI 参数） |
| `workflow` | object | workflow 元数据 |
| `state` | object | 可变的运行时状态（可选，需在 `run()` 签名中声明） |

### agent() 调用

```python
result = agent(
    "提取论文信息。",           # task — WHERE/WHAT（编排指令）
    agent_def="reader",          # 指向 agents/reader.md
    paper_path="...",            # kwargs 对应 agent input schema 的 properties
    language="zh",
    output_dir="./repro-data",
)
```

| 参数 | 说明 |
|------|------|
| `prompt` (positional) | **Task** — 编排层指令，描述"在哪里做什么"。不超过一句话。 |
| `agent_def` | agent 文件名（不含 `.md`），从 `agents/` 目录加载 |
| `**kwargs` | 对应 agent `input` schema 的 properties，用于模板变量替换 |
| `schema` | 可选，覆盖 agent 的 `output` schema |
| `model` | 可选，覆盖 agent 的 `model` 字段 |

**agent() 返回值**：
- agent 无 `output` schema → 返回 `str`（agent 最后一条消息）
- agent 有 `output` schema → 返回 `dict`（结构化输出）

### 典型模式：Phase 重试

```python
report = None
while state.attempt < phase_retries:
    if state.attempt > 0:
        log(f"重试第 {state.attempt} 轮...")

    phase("Provision")
    agent("部署工具容器环境。", agent_def="provision", ...)

    phase("Data")
    agent("下载分析所需数据。", agent_def="data", ...)

    phase("Run")
    agent("运行分析流水线。", agent_def="run", ...)

    phase("Validate")
    report = agent("对比复现结果与论文声称。", agent_def="validate", ...)

    if report and report.get("verdict") != "FAILED":
        break
    state.attempt += 1
```

## Agent 定义

每个 agent 文件（`agents/<name>.md`）包含 YAML frontmatter 和 Markdown body。

### Frontmatter 字段

```yaml
---
name: reader                    # agent 名称（文件 basename）
description: Phase 1 — 提取     # 描述
extends: _base                  # 继承的抽象 agent
model: sonnet                   # 可选，模型覆盖（如多模态需要）
skills:                         # 需要的 skills
  - paperutils
  - mineru-api
input:                          # JSON Schema，参数定义
  type: object
  properties:
    paper_path:
      type: string
      default: ''
  required:
    - language
output:                         # JSON Schema，结构化输出
  type: object
  properties:
    verdict:
      type: string
      enum: [REPRODUCED, FAILED]
  required:
    - verdict
---
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | 是 | 与文件名一致 |
| `description` | 是 | 一句话描述 |
| `extends` | 否 | 继承的抽象 agent（`_` 前缀的文件不暴露给用户） |
| `model` | 否 | 模型覆盖，如 `sonnet`（多模态） |
| `skills` | 否 | 需要的 skill 列表，通过 `extends` 继承合并 |
| `input` | 否 | JSON Schema，定义接受的参数。`properties` 的 key 对应 `agent()` 的 kwargs |
| `output` | 否 | JSON Schema，定义结构化输出格式。有则 `agent()` 返回 dict |
| `mcpServers` | 否 | MCP 服务器列表 |
| `env` | 否 | 需要的环境变量列表 |
| `isolation` | 否 | 隔离模式，如 `worktree` |

### Body 中的模板变量

Body 是 Markdown，使用 `{{ var }}` 引用 `input` schema 中定义的参数：

```markdown
## 运行上下文
- 论文路径: {{ paper_path }}
- 产出语言: {{ language }}
```

变量在运行时通过 `agent()` 的 kwargs 传入并替换。Body 是 HOW（方法论和约束），
描述 agent 应该**如何**完成工作。

### Task 与 Body 的职责分离

| | Body（agent 定义） | Task（agent() 第一个参数） |
|---|---|---|
| 内容 | HOW — 方法论、约束、规则、输出格式 | WHERE/WHAT — 编排层指令 |
| 示例 | "使用 mineru-api 转换 PDF，提取所有声明写入 plan.md" | "提取论文全部声明和资源。" |
| 长度 | 可以很长（数百行） | 一句话 |
| 参数 | 使用 `{{ var }}` 模板 | 无模板 |

Body 不应包含"在哪里找到文件"、"从哪开始"等信息——这些属于编排层，应在 Task 中。
Body 中的路径引用应使用相对路径（如 `01_plan/plan.md`），agent 从 `output_dir` 推导。

### extends 继承规则

- Body：拼接（父在前，子在后）
- `skills` / `env` / `mcpServers`：列表合并
- `input` / `output`：JSON Schema 合并（properties 合并，required 合并）
- 标量字段（`model`、`isolation`）：子覆盖父
- `_` 前缀的 agent 文件不暴露给用户，只作为抽象基类

## _base.md

抽象 agent，定义所有 phase 共享的约定。至少包含：

```yaml
---
name: _base
description: 公共工作约定（抽象 agent，不直接调用）
skills:
  - background-task         # 如有异步任务需求
input:
  type: object
  properties:
    language:               # 几乎所有 loop 都需要
      type: string
    output_dir:             # 几乎所有 loop 都需要
      type: string
  required:
    - language
    - output_dir
---
```

Body 内容：
- 文件与状态约定（产出目录、不覆盖已有文件、Git 提交范围）
- 异步任务约定（使用 background-task skill）
- 代码规范（禁止硬编码路径）
- 产出语言约定
- 辅助工具速查

## pixi.toml

```toml
[workspace]
name = "my-loop"
description = "..."
channels = ["conda-forge", "bioconda"]
platforms = ["osx-arm64", "linux-64"]
version = "0.1.0"

[activation.env]
SKILLS_HOME = "${PIXI_PROJECT_ROOT}/.skills"
# 各 skill 需要的环境变量

[dependencies]
# 系统级依赖（如 openjdk、nextflow）

[tasks]
install-skills = { cmd = "skit install <skill1> && skit install <skill2>" }
check-env = { cmd = "..." }
```

## Gotchas

- `agent_def` 指向文件名（不含 `.md`），不是 agent 的 `name` 字段。
- `state` 参数必须在 `run()` 签名中声明才会传入。用于跨 phase 保持状态（如重试计数）。
- `_base.md` 的 `input` properties 被所有子 agent 继承，子 agent 无需重复声明 `language` 和 `output_dir`。
- `agent()` 无 `output` schema 时返回纯文本，无法用 `.get("verdict")` 取值——先判断类型。
- `extends` 解析是递归的，但不要创建循环继承。
- `{{ var }}` 模板中空格可选：`{{var}}` 和 `{{ var }}` 等价。
- Body 中的路径使用相对路径，运行时从 `output_dir` 推导。不要写绝对路径。
- `skills` 只是声明——对应的 skill 必须通过 `pixi.toml` 的 `install-skills` 安装。