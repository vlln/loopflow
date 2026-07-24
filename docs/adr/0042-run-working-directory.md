---
title: ADR 0042 — Run 显式工作目录
description: 将 run 的工作目录从隐式进程 cwd 提升为 run 的显式属性，create_run 接受 working_directory，executor 子进程 chdir 执行，修复 WebUI 模式下所有 run 落在 server 启动目录的架构缺口
type: adr
status: proposed
created: 2026-07-24T05:30:00Z
---

# ADR 0042: Run 显式工作目录

## Context

当前 run 的工作目录被硬编码为进程 cwd：

- `execution.py` `RunExecutor.start()`：`working_directory = Path.cwd()`，run 目录按 `runs_root / lf_{encoded(working_directory)} / run_id` 组织
- 同处 observer 初始化：`FileChangeObserver(working_dir=Path.cwd())`
- REST `create_run` 只接受 `{loop, args, backend, model, mock, from_phase, only_phase}`，无 working_directory 字段

这导致一个模式差异：**headless 正确，WebUI 错误**。

- headless：用户 `cd` 到目标项目再执行 `loopflow run`，进程 cwd 即目标目录，行为符合直觉
- WebUI：一个常驻 server 进程服务所有 run，所有 run 的工作目录和文件观察目录都落在 server 的启动目录——用户无法在创建 run 时选择工作目录，文件变化观察树展示的也是 server 目录而非用户意图的项目目录

存储设计其实早已预留多工作目录：`runs_root` 按 `lf_{encoded(working_directory)}` 分命名空间，`append_run_index` 也接收 working_directory 参数。原设计预期过这个能力，只是执行层与 API 没有打通。

需要明确的是：CLI 同时提供 `run`（一次性执行）与 `serve`（常驻服务）双职责是标准 Unix 模式，不是缺陷。**缺陷是 run 的工作目录是隐式继承的进程状态，而不是 run 的显式属性。** Server 是 job runner，job 应自带上下文。

## Decision

### 1. working_directory 是 run 的显式属性

`POST /api/v1/runs` 接受可选字段 `working_directory`：

- 必须是**绝对路径**，且**已存在**、**是目录**；不满足时返回 `422 validation_failed`（details 指明原因：not_absolute / not_found / not_a_directory）
- 缺省时保持现状（进程 cwd），完全向后兼容
- 持久化到 `run.json`，recover / rerun / reconcile 沿用原目录，不接受新值覆盖

### 2. 子进程 chdir，而不是路径传递

`RunExecutor.start()` 将 `working_directory` 传入 multiprocessing 子进程，子进程入口第一行 `os.chdir(working_directory)`。之后：

- workflow 执行、Agent 进程启动、`Path.cwd()` 的全部使用点自然归位
- 文件观察器继续用 `Path.cwd()` 初始化，无需改动观察层代码
- run_dir 命名空间（`lf_{encoded}`）与 `append_run_index` 按现有逻辑自然正确

选择 chdir-in-child 而非把 working_dir 参数穿透所有调用点：进程 cwd 是所有既有代码（含第三方 backend 启动）的隐式契约，穿透传参会把隐式契约扩散成显式参数地狱。

### 3. 安全边界：任意已存在目录

本地单用户工具，server 由用户自己启动，信任使用者的输入。仅校验「绝对路径 + 已存在 + 是目录」，不维护白名单根目录。未来若 server 面向多用户暴露，再引入 allow-root 配置。

### 4. WebUI 创建入口

New Run 对话框增加 working directory 文本输入，默认留空（= server cwd），占位符提示当前 server cwd。queue / scheduler 的 worker 走同一个 `executor.start()`，一并受益。

## Alternatives

| 方案 | 评估 |
|------|------|
| **shell-out wrapper**：server 每次以 `loopflow run --dir X` 起子进程 | 暂缓。隔离性更好、传参更"自然"，但需重写 executor 契约（进程管理、stop/cancel 信号路径、恢复机制）并承担启动开销。本地单用户场景 chdir-in-child 已足够；0076 厘清执行契约后未来升级成本更低。若引入多租户或强隔离需求，重启本方案 |
| **独立 serve 二进制 / 拆分 CLI** | 不采纳。双职责 CLI 是标准模式，问题不在入口合一而在参数缺失；拆分不解决任何实际问题，还增加发布与发现成本 |
| **working_dir 参数穿透所有调用点** | 不采纳。见 Decision 2，进程 cwd 是既有隐式契约，穿透传参扩散改动面且易遗漏（backend 启动、observer、workflow 内用户代码的相对路径） |

## Consequences

- REST 面获得在任意已存在目录启动 run 的能力；这是用户确认的边界
- WebUI 下文件变化观察树展示的是用户指定的项目目录，符合直觉（修复 ADR-0039 在 WebUI 模式的目录错误）
- 旧 run（run.json 无 working_directory 字段）行为与展示不变
- headless 用法不变（`cd` + `loopflow run`）

## Architecture Boundary

工作目录的解析与校验发生在 API 层（`application/web.py` create_run）；chdir 发生在执行层子进程入口（`application/execution.py`）；observer 与 workflow 不感知本 ADR。

## Verification

非技术选型类 ADR：复用既有 multiprocessing 执行模型与 `os.chdir` 标准库，无新依赖、新协议或新框架，豁免 spike 验证。可行性由 0076 容器的 AC-025 自动化测试直接证明（REST 传参 → 子进程 chdir → 观察目录正确 的端到端链路）。
