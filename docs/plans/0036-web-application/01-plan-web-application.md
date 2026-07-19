---
title: Web Application 服务 Plan
description: 实现 CLI/Web 共享的 Run、Phase、Loop、Queue、Backend 查询与命令服务，以及 v2/legacy 事件和生命周期持久化。
type: plan
status: done
created: 2026-07-19T00:00:00Z
---

# Context

现有 CLI 将路径扫描、状态转换、workflow 执行和文本表示混合在 command 函数中；运行时仍写 legacy 事件并直接覆盖 JSON。ADR 0033 要求 CLI/Web 共享 application services，ADR 0034 要求 v2 event envelope、明确 occurrence/call 关联、原子 metadata/state 写和 PID identity。

# Request

实现与 HTTP 无关的结构化应用服务和基础设施 ports，使后续 Web API 只能协调 DTO/错误，不直接拼路径、解析 CLI 输出或修改 Run 文件。

# Output Format

- `src/loopflow/application/web.py`：查询/命令 facade、DTO 与 typed application errors。
- `src/loopflow/infrastructure/web_*.py`：Run/Loop/Event/process/Backend 文件和系统适配。
- 现有 runtime/CLI 复用同一 writer/lifecycle 服务，不产生第二套状态规则。
- Python 单元、集成和契约测试；Report 记录 AC、commit、JUnit 与 coverage。

# Constraints

1. application 不依赖 HTTP、Click、React 或测试目录。
2. `state.json` 保持纯 workflow state；`run.json`/`state.json` 分别原子替换。
3. `<seq>.jsonl` 保持扁平 resume cache；只有 `events.jsonl` 使用 v2 envelope。
4. legacy 歧义标记 unattributed，不按邻近位置推断。
5. Loop preview resolve 后必须仍在 Loop root，拒绝绝对路径、`..` 和 symlink escape。
6. 不实现 Web server、HTTP 状态码或 UI。

# Checkpoint

| 检查点 | 通过条件 | 证据 |
|--------|----------|------|
| Run model | unreadable、stale、graph、occurrence、call、unattributed/malformed DTO 正确 | `e1f7ebe`；Web 单元测试 27 passed |
| Lifecycle | start/stop/resume/rerun/reconcile 状态约束与原子写正确 | `e1f7ebe`；后台 executor 与 lifecycle tests |
| Events | v2 严格递增、legacy 保真、半行容忍、SSE reader cursor primitive | `e1f7ebe`；event projection/replay tests |
| Loops/Queue | 分页模型、invalid Loop、受限 preview、queue DTO 正确 | `e1f7ebe`；resource/application tests |
| Backends | 真实 capabilities/diagnostic DTO、timeout/encoding/secret redaction 正确 | `e1f7ebe`；Backend repository tests |
| Reuse | runtime/CLI 写路径复用 writer/lifecycle primitive | `e1f7ebe`；全量 CLI/runtime 回归 |
| Quality | 新增 Python 代码 >=80% coverage，MR required checks 全绿 | 本地 MR gate：262 passed、82.50%、Chromium 3/3、wheel pass |

# Steps

1. TDD 定义 application DTO、errors、pagination 与 repository ports。
2. 实现 atomic JSON、Run index/detail、PID identity 和 stale/reconcile。
3. 实现 v2 writer/reader、legacy reader、Phase graph/occurrence/call projection。
4. 实现 Loop discovery/preview、Queue 和 Backend diagnostics projection。
5. 提取 start/stop/resume/rerun coordination，并让现有 runtime/CLI 复用持久化 primitive。
6. 跑 unit/integration/contract、coverage、MR gate，完成 Report 与提测门禁。

# Acceptance

- AC-014-N-4
- AC-014-N-5
- AC-014-N-6
- AC-014-N-7
- AC-014-E-1
- AC-014-E-2
- AC-014-F-1
- AC-014-F-2
- AC-015-N-1
- AC-015-N-2
- AC-015-N-3
- AC-015-N-4
- AC-015-N-5
- AC-015-B-1
- AC-015-B-2
- AC-015-E-1
- AC-015-E-2
- AC-015-F-1
- AC-015-F-2
- AC-017-B-1
- AC-017-B-2
- AC-017-E-1
- AC-017-E-2
- AC-017-F-1
- AC-017-F-2
- AC-018-N-1
- AC-018-N-2
- AC-018-B-1
- AC-018-B-2
- AC-018-E-1
- AC-018-E-2
- AC-018-F-1
- AC-018-F-2
