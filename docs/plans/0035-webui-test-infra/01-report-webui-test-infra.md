---
title: WebUI 测试与交付底座 Report
description: 记录 WebUI 测试基础设施的实现、反向自证、覆盖率、浏览器、CI 与 wheel 冒烟证据。
type: report
status: complete
created: 2026-07-19T00:00:00Z
---

# 结果

WebUI 一次性测试与交付基础设施已完成。PR #1 在故意失败提交时被 required checks 阻断，恢复后 Python、frontend、browser、wheel 五类 checks 全绿。

## 产出

- `web/`：Node 22、React/Vite、Vitest/Testing Library、Playwright Chromium 和三视口配置。
- `tests/web_support/`：Run/Loop/Event/Backend/process/time fixtures、Interface schema 和 HTTP/SSE helper。
- `tests/system/cases.json`：AC-014..019 共 60 个场景的机器清单。
- `scripts/mr-gate.sh`、`submission-gate.py`：MR 与提测门禁。
- GitHub Actions：Python 3.10/3.14、frontend、browser、wheel 独立 jobs。
- wheel 流水线：生产构建、资产同步、隔离安装与 `importlib.resources` 冒烟。

## 门禁证据

| 门禁 | 结果 | 证据 |
|------|------|------|
| 测试工具链 | PASS | run `29672196161` 五项 required checks 全绿 |
| MR 正确拦截 | PASS | commit `eee2fd1` 使 Python checks 失败；PR #1 `mergeStateStatus=BLOCKED`；commit `29e8859` 恢复 |
| 提测正确拦截 | PASS | invalid Report、unknown AC、79.99% coverage、failed JUnit 四类反例均被拒绝 |
| Mock/fixture 契约 | PASS | Run/Loop/Queue/Backend/Diagnostic/v2 Event schema 通过；额外 health_score 被拒绝 |
| 覆盖率准确性 | PASS | 已知 2 分支均执行，pytest-cov 报告 2/2、100% |
| 浏览器冒烟 | PASS | 1440x900、1024x768、390x844 Chromium 页面非空、无水平滚动，各产出 smoke.png 与 trace.zip |
| AC 静态覆盖 | PASS | 60 scenarios 完整；漏项、错误 410 映射、空断言和 strict planned node 均被拒绝 |
| wheel 静态资产 | PASS | Python 3.10 隔离环境读取 index.html 和 2 个 hashed assets |

## 变更

- `23dd4ab`：全栈测试基础设施主体。
- `7c250a6`：排除 TypeScript build cache。
- `24c14fb`：贡献与门禁说明。
- `8fdd1d8`：localhost proxy 隔离。
- `40c1c61`：消除既有 resume cache 单测的主机 Backend 依赖。
- `7353246`：修正 DDD 重构后的 coverage omit 路径。
- `eee2fd1` / `29e8859`：远端失败阻断与恢复证据。
- `a5b4029`：保留三视口成功截图与 trace 证据。

## 遗留风险

- `tests/system/cases.json` 的 test nodes 在 TEST_INFRA 保持 `planned::`；进入 DEVELOP 后各 Plan 必须替换为真实 pytest/Playwright node，strict checker 会拒绝未完成项。
- 当前前端仅为 tests-only infrastructure shell，不代表产品 UI，也不作为视觉基线。
- `develop` 已配置 browser、frontend、python (3.10)、python (3.14)、wheel 五项 required checks，并对管理员生效。
