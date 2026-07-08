---
title: loopflow AC
description: loopflow 核心功能验收标准：loop 定义、运行、resume、实例管理、parallel/pipeline/workflow
type: ac
status: active
created: 2026-07-07T12:00:00Z
---

# AC-001: Loop 定义与运行

验证开发者能否定义 loop 并通过 CLI 运行。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-001-N-1 | `~/.loopflow/loops/hello/` 目录存在，含 workflow.py（定义 `run()` 函数，调用 `agent("say hello")` 并返回结果）和 agent 定义文件 | 执行 `loop run hello` | CLI 输出 agent 返回的文本，运行实例在 `~/.loopflow/runs/<run-id>/` 下创建，`run.json` 中 status=done，序号 jsonl 文件存在 | 自动化 |
| AC-001-N-2 | 同 AC-001-N-1，但 workflow.py 使用 `args` 参数 | 执行 `loop run hello --args '{"name":"World"}'` | workflow.py 内部 `args["name"]` 值为 `"World"`，agent 收到包含 World 的 prompt | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-001-B-1 | 同 AC-001-N-1 | 执行 `loop run hello`，workflow.py 中 `run()` 返回 `None` | 运行正常完成，status=done，无 stdout 输出 | 自动化 |
| AC-001-B-2 | `~/.loopflow/loops/empty/` 目录存在，workflow.py 中 `run()` 函数体为 `pass` | 执行 `loop run empty` | 运行正常完成，status=done，无 agent 调用 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-001-E-1 | `~/.loopflow/loops/bad/` 目录存在，workflow.py 缺少 `run()` 函数 | 执行 `loop run bad` | CLI 报错退出，退出码非零，stderr 提示缺少 run() 函数 | 自动化 |
| AC-001-E-2 | `~/.loopflow/loops/bad/` 目录存在，workflow.py 有语法错误 | 执行 `loop run bad` | CLI 报错退出，退出码非零，stderr 包含 Python 语法错误信息 | 自动化 |
| AC-001-E-3 | loop 名称不存在 | 执行 `loop run nonexistent` | CLI 报错退出，stderr 提示 loop 未找到 | 自动化 |
| AC-001-E-4 | agent 定义文件缺少 `name` 字段 | 执行 `loop run <name>` | CLI 报错退出，stderr 提示 agent 定义不完整 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-001-F-1 | Agent 后端不可用（如 kimi CLI 未安装） | 执行 `loop run hello`，workflow.py 调用 `agent()` | CLI 报错退出，stderr 提示后端不可用，提供安装指引 | 自动化 |
| AC-001-F-2 | Agent 后端执行超时或崩溃 | 执行 `loop run hello`，backend 进程异常退出 | `agent()` 返回 None，workflow.py 中可用 `None` 检测处理，运行不崩溃 | 自动化 |

---

# AC-002: Resume 崩溃恢复

验证 loop 运行中断后，resume 能正确恢复。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-002-N-1 | workflow.py 中依次调用 3 个 agent：`agent("step1")`、`agent("step2")`、`agent("step3")`。首次运行时在 step2 中途崩溃（模拟：第 2 个 jsonl 文件不存在） | 执行 `loop resume <run-id>` | step1 从缓存返回（不真正执行），step2 和 step3 真正执行，最终 status=done，3 个 jsonl 文件均存在 | 自动化 |
| AC-002-N-2 | 同 AC-002-N-1，但所有 agent 调用已完成 | 执行 `loop resume <run-id>` | 所有 agent 调用从缓存返回，不真正执行后端，status 保持 done | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-002-B-1 | workflow.py 中有 while 循环，迭代 5 次，每次调用 `agent()`。首次运行在第 3 次迭代崩溃 | 执行 `loop resume <run-id>` | 前 3 次 agent 调用从缓存返回，第 4、5 次真正执行，while 循环正确退出 | 自动化 |
| AC-002-B-2 | run-id 不存在 | 执行 `loop resume nonexistent` | CLI 报错退出，stderr 提示 run 未找到 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-002-E-1 | 运行实例正在执行中（status=running） | 执行 `loop resume <run-id>` | CLI 报错退出，提示实例正在运行，不可并发 resume | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-002-F-1 | 缓存 jsonl 文件存在但损坏（非合法 JSON） | 执行 `loop resume <run-id>` | 损坏的缓存视为未完成，重新执行该 agent 调用，覆盖损坏文件 | 自动化 |

---

# AC-003: 运行实例管理

验证 status、list、stop 命令的正确性。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-003-N-1 | 存在运行实例 `abc123`，status=done，有 3 个 agent 调用 | 执行 `loop status abc123` | 输出 loop 名称、run_id、status=done、agent 调用数量、每个调用的耗时 | 自动化 |
| AC-003-N-2 | 存在多个运行实例，至少一个 running | 执行 `loop list` | 列出所有实例的 run_id、loop 名称、status、创建时间 | 自动化 |
| AC-003-N-3 | 存在 running 状态的实例 | 执行 `loop stop <run-id>` | 实例被终止，status 变为 stopped，后台进程被杀 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-003-B-1 | 没有任何运行实例 | 执行 `loop list` | 输出空列表或"No runs found"，退出码为 0 | 自动化 |
| AC-003-B-2 | run-id 不存在 | 执行 `loop status nonexistent` | CLI 报错退出，提示 run 未找到 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-003-E-1 | 运行的实例 pid 文件存在但进程已不存在 | 执行 `loop stop <run-id>` | CLI 提示进程已不存在，清理 pid 文件和 lock，status 设为 stopped | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-003-F-1 | `~/.loopflow/runs/` 目录不可读（权限问题） | 执行 `loop list` | CLI 报错退出，stderr 提示权限问题 | 自动化 |

---

# AC-004: Parallel 并发调用

验证 workflow.py 中 `parallel()` 的正确性。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-004-N-1 | workflow.py 中 `parallel([lambda: agent("a"), lambda: agent("b"), lambda: agent("c")])` | 执行 `loop run <name>` | 3 个 agent 调用并发执行，全部完成后返回结果列表，顺序与输入一致 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-004-B-1 | `parallel([])` 空列表 | 执行 `loop run <name>` | 返回空列表，不报错 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-004-E-1 | parallel 中某个 thunk 抛出异常 | 执行 `loop run <name>` | 对应位置返回 None，其他 thunk 正常完成，整体不崩溃 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-004-F-1 | parallel 中某个 agent 后端不可用 | 执行 `loop run <name>` | 对应 agent 返回 None，其他 agent 正常完成 | 自动化 |

---

# AC-005: Pipeline 流水线

验证 workflow.py 中 `pipeline()` 的正确性。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-005-N-1 | workflow.py 中 `pipeline(["a", "b"], stage1, stage2)`，每个 stage 调用 `agent()` | 执行 `loop run <name>` | 每个 item 独立流经两个 stage，item "a" 可在 stage2 时 item "b" 仍在 stage1 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-005-B-1 | `pipeline([], stage1)` 空 items | 执行 `loop run <name>` | 返回空列表，不报错 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-005-E-1 | pipeline 中某个 stage 返回 None | 执行 `loop run <name>` | 该 item 的后续 stage 被跳过，其他 item 继续正常处理 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-005-F-1 | pipeline 中某个 stage 的 agent 调用全部失败 | 执行 `loop run <name>` | 该 item 返回 None，不影响其他 item | 自动化 |

---

# AC-006: Workflow 嵌套

验证 workflow.py 中 `workflow()` 嵌套调用的正确性。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-006-N-1 | 主 workflow.py 中调用 `workflow("other/workflow.py", {"key": "val"})`，子 workflow 正常执行 | 执行 `loop run <name>` | 子 workflow 的 agent 调用在主 workflow 的 run 实例中记录，子 workflow 的 `args` 正确传递 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-006-B-1 | 子 workflow 脚本路径不存在 | 执行 `loop run <name>` | `workflow()` 返回 None，主 workflow 不崩溃 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-006-E-1 | 子 workflow 的 `run()` 函数不存在 | 执行 `loop run <name>` | `workflow()` 返回 None，主 workflow 不崩溃 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-006-F-1 | 子 workflow 中 agent 后端不可用 | 执行 `loop run <name>` | 子 workflow 内部 agent 返回 None，`workflow()` 返回值反映失败状态 | 自动化 |

---

# AC-007: Loop 发现与加载

验证 CLI 能正确扫描和加载 loop 定义。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-007-N-1 | `~/.loopflow/loops/` 下存在 2 个合法 loop 目录 | 执行 `loop list` | 输出 2 个 loop 的名称和描述（从 workflow.py 的 `meta` 提取） | 自动化 |
| AC-007-N-2 | loop 目录含 `agents/` 子目录，有 2 个 agent 定义文件 | 执行 `loop run <name>` | 两个 agent 均被正确解析，workflow.py 中可引用 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-007-B-1 | `~/.loopflow/loops/` 目录为空 | 执行 `loop list` | 输出空列表，退出码为 0 | 自动化 |
| AC-007-B-2 | `~/.loopflow/loops/` 目录不存在 | 执行 `loop list` | 创建空目录，输出空列表，不报错 | 自动化 |
| AC-007-B-3 | agent 定义文件 body 为空（无系统提示词） | 执行 `loop run <name>` | 正常执行，使用后端默认系统提示词 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-007-E-1 | workflow.py 的 `meta` 不是纯字面量（含变量引用） | 执行 `loop run <name>` | CLI 报错退出，stderr 提示 meta 格式错误 | 自动化 |
| AC-007-E-2 | agent 定义文件 YAML frontmatter 格式错误 | 执行 `loop run <name>` | CLI 报错退出，stderr 提示具体 agent 文件解析失败 | 自动化 |
| AC-007-E-3 | loop 目录缺少 workflow.py | 执行 `loop run <name>` | CLI 报错退出，stderr 提示缺少 workflow.py | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-007-F-1 | `~/.loopflow/loops/` 目录不可读（权限问题） | 执行 `loop list` | CLI 报错退出，stderr 提示权限问题 | 自动化 |

---

# AC-008: Agent 后端管理

验证后端自动检测、手动指定、不可用降级。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-008-N-1 | 系统 PATH 中存在 kimi CLI | 执行 `loop run hello`（不指定 --backend） | 自动检测到 kimi 后端并使用 | 自动化 |
| AC-008-N-2 | 系统 PATH 中存在多个后端 | 执行 `loop run hello --backend claude` | 使用 claude 后端，忽略其他可用后端 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-008-B-1 | 系统 PATH 中无任何后端 | 执行 `loop run hello` | CLI 报错退出，stderr 列出所有支持的后端和安装指引 | 自动化 |
| AC-008-B-2 | 指定的后端名称不在支持列表中 | 执行 `loop run hello --backend unknown` | CLI 报错退出，stderr 列出可用后端名称 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-008-E-1 | 后端二进制存在但无法正常启动（如未认证） | 执行 `loop run hello` | CLI 输出警告信息（如认证引导），但继续尝试执行 | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|---------|---------|---------|---------|
| AC-008-F-1 | 后端进程在 agent 调用中途崩溃 | 执行 `loop run hello`，workflow.py 调用 `agent()` | `agent()` 返回 None，运行不崩溃，stderr 记录错误信息 | 自动化 |