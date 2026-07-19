---
title: WebUI 测试与交付底座 Plan
description: 搭建 WebUI 的 Python、HTTP、前端、浏览器、视觉、契约、覆盖率、CI 与提测门禁并完成反向自证。
type: plan
status: done
created: 2026-07-19T00:00:00Z
---

# 目标

依据 ADR 0035 搭建一次性测试基础设施，证明它能运行且能拒绝失败输入，为 DEVELOP 阶段实现 AC-014..019 提供确定性环境。

# Constraints

1. 不实现 Interface 0001 的业务 endpoint、Run 生命周期或三个 WebUI 工作区。
2. `references/DESIGN.md` 只作为后续视觉断言的事实源；不修改或提交 `references/`。
3. Python 产品运行时不新增 Web 框架；Node 与 Chromium 仅是开发/CI 依赖。
4. 测试数据只写 pytest/Playwright 临时目录，不读取用户真实 Runs、Loops 或 credentials。
5. 文档变更与基建代码分别提交。

# Steps

1. 创建 `web/` 工作区，固定 Node 22、React/Vite/Vitest/Testing Library/Playwright 版本，加入 typecheck、component coverage、build 和 Chromium 冒烟入口。
2. 创建 Python Run/Loop/Backend/process/time fixture 工厂及 HTTP/SSE 黑盒 helper，以 schema 检查 Interface 0001 DTO 与错误信封。
3. 创建 `tests/system/cases.json` 与静态检查器，验证 AC-014..019 全场景、N/B/E/F、endpoint/status/event 和关键断言元数据。
4. 创建 `scripts/mr-gate.sh` 与 `scripts/submission-gate.py`，配置 coverage machine output、Report/Plan/AC 一致性检查和反向失败 fixtures。
5. 配置 GitHub Actions 的 Python 3.10/3.14、Node 22、Playwright Chromium、dependency audit 和 wheel 静态资产隔离冒烟。
6. 更新 CONTRIBUTING.md 的测试命令、目录、MR 与提测流程。
7. 执行基建自证：故意失败测试、invalid Report、缺失 AC、低 coverage、错误 mock shape 均被拒绝；已知分支覆盖率准确；浏览器与 wheel 冒烟通过。
8. 回填 ADR Verification 与本 Report，独立复核后将 Plan 标记 done。

# Checkpoint

| 检查点 | 通过条件 | 证据 |
|--------|----------|------|
| Toolchain | lockfile 安装、typecheck、Vitest、Vite build、Playwright Chromium 冒烟通过 | run `29672196161` frontend/browser |
| Contract | Interface-shaped fixtures 全部通过，错误 shape 被拒绝 | commit `23dd4ab`；Python 3.10/3.14 checks |
| AC manifest | AC-014..019 全场景对齐，缺失/错误 endpoint/status/event 被拒绝 | 60 scenarios；`test_ac_manifest.py` |
| MR gate | 故意失败时非零，恢复后全绿；远端 required check 证据可核验 | PR #1；`eee2fd1` BLOCKED；run `29672196161` 全绿 |
| Submission gate | invalid Report、AC 和 coverage fixtures 全部被拒绝 | `test_submission_gate.py` 四类反例 |
| Coverage | 已知分支 fixture 的工具结果与人工统计一致 | 2/2 branches，100% |
| Wheel | 隔离安装后通过 importlib.resources 读取 index 与 hashed asset | run `29672196161` wheel |
| Scope | 无 Web API、Run 生命周期或工作区产品实现 | `git diff 34aa8ee..29e8859` 内容审查 |

# Exit

全部 Checkpoint 通过、ADR 0035 验证证据回填、Report complete 且分支合并到 `develop` 后，才可推进到 DEVELOP。
