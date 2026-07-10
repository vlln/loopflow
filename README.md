# loopflow

AI Agent 循环编排工具。用 Python 定义工作流，通过 CLI 运行和恢复。

## 5 分钟快速开始

### 1. 安装

```bash
pip install loopflow
```

### 2. 创建第一个 loop

```bash
mkdir -p ~/.loopflow/loops/hello/agents
```

**`~/.loopflow/loops/hello/workflow.py`**：

```python
meta = {"name": "hello", "description": "我的第一个 loop"}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    phase("Research")
    result = agent("一句话介绍什么是 loopflow")
    log(f"Research done: {len(result or '')} chars")

    phase("Translate")
    result = agent(f"把下面这句话翻译成中文: {result}")
    log(f"Translate done: {result}")

    return result
```

**`~/.loopflow/loops/hello/agents/default.md`**：

```markdown
---
name: default
description: Default agent
---
You are a helpful assistant. Answer concisely.
```

### 3. 运行

```bash
loop run hello
```

```
[loopflow] Running: hello (a1b2c3d4)
[loopflow] Phase: Research
[loopflow] Calling agent via auto...
[loopflow] Agent responded: 256 chars
[loopflow] Phase: Translate
[loopflow] Calling agent via auto...
[loopflow] Done: a1b2c3d4
```

---

## 概念

| 概念 | 一句话 |
|------|--------|
| **Loop** | 一个文件夹，包含 `workflow.py` + `agents/`，定义了一个 AI 工作流 |
| **Phase** | 工作流中的一个阶段，例如"研究"→"翻译"→"验证" |
| **Agent** | 一次 AI 调用。`agent("指令")` 把指令发给 AI 后端，返回结果 |
| **Run** | Loop 的一次执行实例，有唯一 ID，状态持久化到磁盘 |
| **Resume** | 崩溃恢复。重新执行 workflow.py，已完成的 agent 调用自动跳过 |

### 执行模型

```
workflow.py 从头跑到尾。
  └─ phase("A")        → 标记一个阶段
       └─ agent("...")  → 调用 AI，返回结果
       └─ agent("...")  → 可以在一个 phase 里调多次
  └─ phase("B")
       └─ agent("...")
  └─ return
```

关键：`workflow.py` 每次 `run` / `resume` 都会从头执行。但 `agent()` 调用会根据序号缓存——已完成的不重复执行。

---

## 创建 Loop

### 目录结构

```
~/.loopflow/loops/<name>/
├── workflow.py          # 必需。def run(agent, parallel, pipeline, phase, log, args, workflow)
└── agents/              # 可选。agent 定义文件
    └── <name>.md        # YAML frontmatter + Markdown body
```

### workflow.py

```python
meta = {
    "name": "my-loop",
    "description": "这个 loop 做什么",
    "phases": [                          # 可选：声明预期阶段
        {"title": "Research", "detail": "收集信息"},
        {"title": "Translate", "detail": "翻译结果"},
        {"title": "Verify", "detail": "验证准确性"},
    ],
    "state": {                           # 可选：声明持久化状态
        "attempt": 0,                    # 默认值，类型即约定
    },
}

def run(agent, parallel, pipeline, phase, log, args, workflow, state):
    # state.attempt += 1  # 每次 agent() 成功后自动保存
    return result
```

### Agent 定义文件

```markdown
---
name: translator
description: 专门负责翻译
requires:
  params:
    - target_language
---
你是一个专业翻译。将输入内容翻译成 {{target_language}}。
```

引用方式：

```python
agent("需要翻译的内容", agent_def="translator", target_language="中文")
```

---

## API 参考

### `agent(prompt, **opts) → str | dict | None`

调用 AI Agent 执行任务。

| 参数 | 类型 | 说明 |
|------|------|------|
| `prompt` | `str` | 任务指令（必填） |
| `agent_def` | `str` | 使用的 agent 定义文件名（不含 `.md`），默认 `"default"` |
| `schema` | `dict` | JSON Schema，要求 agent 返回结构化 JSON |
| `max_retries` | `int` | schema 合规重试次数，默认 3 |
| `backend` | `str` | 指定后端（kimi/claude/codex 等），默认自动检测 |
| `model` | `str` | 指定模型 |
| `isolation` | `str` | `"worktree"` 时在独立 git worktree 中执行 agent，并发安全 |
| `**kwargs` | | 传递给 agent 定义模板的参数（如 `target_language="中文"`） |

返回值：`schema` 或 `output` 指定时返回 `dict`，否则返回 `str`。infra 失败抛 `AgentError`。

### `phase(title: str)`

标记一个阶段开始。后续 `agent()` 调用自动归属到该阶段。影响执行图和日志。

### `log(message: str)`

输出一条日志。写入 events.jsonl，在 watch 模式下正常显示。

### `parallel(thunks: list) → list`

并行执行多个函数。所有函数同时启动，等待全部完成。

```python
results = parallel([
    lambda: agent("分析数据A"),
    lambda: agent("分析数据B"),
    lambda: agent("分析数据C"),
])
```

### `pipeline(items: list, *stages) → list`

对每个 item 依次通过所有 stage 处理。不同 item 独立并发。

```python
results = pipeline(
    ["论文A", "论文B", "论文C"],
    lambda item, idx: agent(f"阅读 {item}"),
    lambda text, item, idx: agent(f"总结 {item}"),
)
```

### `workflow(script_path: str, args: dict) → Any`

嵌套调用另一个 workflow.py。

### `args`

`loop run` 时 `--args '<json>'` 传入的参数，在 workflow.py 中通过 `args` 参数访问。

### `state`

声明式持久化状态。`meta.state` 中声明默认值，workflow 中通过 `state.key` 属性访问。每次 `agent()` 成功后自动保存到 `state.json`，resume 时自动恢复。

```python
meta = {"state": {"attempt": 0}}

def run(agent, ..., state):
    state.attempt += 1  # 自动持久化，resume 恢复

---

## CLI 参考

### `loop run <name>`

启动一个 loop。每次运行创建新的实例和 ID。

```bash
loop run hello                           # 运行
loop run hello --args '{"key": "val"}'   # 传参
loop run hello --mock bash               # mock: shell 执行（兼容旧用法）
loop run hello --mock auto               # mock: 根据 schema 自动生成数据
loop run hello --watch                   # 实时显示执行图
```

### `loop resume <run-id>`

恢复崩溃的运行。已完成的 agent 调用自动跳过。

```bash
loop resume a1b2c3d4
```

### `loop status <run-id>`

查看运行状态。

```bash
loop status a1b2c3d4           # 基本信息
loop status a1b2c3d4 --graph   # 含执行图
loop status a1b2c3d4 --no-graph # 不含执行图
```

### `loop list`

列出所有 loop 定义和运行实例。

### `loop stop <run-id>`

停止正在运行的实例。

---

## 执行图

loopflow 自动记录 phase 之间的转移关系，在运行结束时渲染执行图：

```
  Start ──→ Research ──→ Translate ──→ Verify
```

分支和循环也会被正确渲染：

```
  Start ──→ PathA ──→ PathA-End
   │
   └──→ PathB ──→ PathB-End
   └── Start (第2轮, 回边)
```

使用 `--watch` 可以在运行过程中实时看到图的增量更新。

---

## 崩溃恢复

`loop run` 运行中如果进程崩溃（Ctrl+C、断电、网络断开），可以 `loop resume <run-id>` 恢复：

1. `workflow.py` 从头重新执行
2. 每个 `agent()` 调用检查序号缓存——如果该序号已完成且 exit_code=0，直接返回缓存结果
3. 未完成的调用正常执行

这意味着：**你的 workflow.py 可以保持幂等——写一次，崩溃无数次，resume 总能回到断点继续。**

---

## 后端

loopflow 自动检测可用的 AI Agent 后端：

| 后端 | 对应的 CLI 工具 |
|------|----------------|
| kimi | `kimi` |
| claude | `claude` |
| codex | `codex` |
| gemini | `gemini` |
| qwen | `qwen` |
| ... | ... |

也可以显式指定：`agent("...", backend="claude")`。

没有安装任何后端时，可以用 `--mock` 模式测试——prompt 作为 shell 命令执行。

---

## 更多示例

```bash
ls ~/.loopflow/loops/
# hello/       — 最简示例
# branch-demo/ — 多分支工作流
# demo-graph/  — 执行图展示
```

每个示例都是一个完整的 loop，可以直接 `loop run <name>` 运行。