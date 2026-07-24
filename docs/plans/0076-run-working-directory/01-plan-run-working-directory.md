---
title: Run 显式工作目录与观察语义 Plan
description: 实现 ADR-0042 显式工作目录、ADR-0043 基线快照、BR-046 文件预览（AC-025 全场景 + AC-024-B-1/B-8/N-8）
type: plan
status: pending
created: 2026-07-24T05:45:00Z
---

# Goal

按冻结契约实现三个方向：run 显式工作目录（ADR-0042 / AC-025）、文件观察基线快照（ADR-0043 / AC-024-B-1,B-8）、run 工作目录文件预览（BR-046 / AC-025-N-4,N-5,B-4,B-5,E-3）。

# Constraints

- 后端零外部依赖（标准库），不引入新依赖
- `working_directory` 缺省 = 进程 cwd，完全向后兼容
- recover / rerun 沿用 run.json 持久化的 working_directory，recover 请求体中的该字段拒绝或忽略
- 文件预览端点必须 resolve 限定在 run 工作目录内（403 path_forbidden），文本上限 1 MiB（422 file_not_previewable）
- 基线为内存态，file_changes.jsonl 格式不变；legacy run 行为不变
- 前端沿用 PanelHeader/SectionHeader 抽象与既有样式标尺

# Steps

1. 后端：`web.py` create_run 校验（not_absolute/not_found/not_a_directory → 422）+ executor `working_directory` 参数 + 子进程 `os.chdir` + run.json 持久化
2. 后端：`FileChangeObserver.seed()` 基线 + execution.py 启动时调用
3. 后端：`GET /api/v1/runs/{run_id}/file?path=` 端点（application/web.py 读模型 + server.py 路由）
4. 前端：api.ts（createRun 字段 + runFile）、NewRunDialog 输入、文件树点击预览对话框
5. 测试：AC-025 自动化；AC-024-B-1 重映射为基线断言 + B-8 新增；manifest.py 同步；前端对话框/预览测试
6. 全量验证：pytest、前端 vitest/typecheck/build/e2e、静态资源同步

# Acceptance

- AC-025-N-1..N-5, B-1..B-5, E-1..E-3, F-1
- AC-024-B-1（基线语义）、AC-024-B-8、AC-024-N-8
- 既有 Python 385 + 前端 21 测试全部回归通过

# Checkpoint

- 后端完成并通过 AC-025/AC-024 相关测试后，前端才开始联调预览端点
- 合入前必须通过 MR 门禁（scripts/mr-gate.sh，如适用）与全量测试

# Exit

全部 Acceptance 通过，写 Report，合并到 develop。
