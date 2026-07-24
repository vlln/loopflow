---
title: Agent Structured Intervention Implementation Report
description: 记录 Agent structured intervention vNext 实现结果
type: report
status: complete
created: 2026-07-23T18:30:00Z
---

# Summary

已实现 AC-023 Agent structured intervention vNext。Agent 可通过 `__loopflow.requests[]` 返回多个人工介入请求；workflow `intervene()` 保留路由门控语义并支持 `options/allow_custom`；Web API 支持 batch respond all-or-nothing；WebUI 支持多问题一次提交。

# Results

- `src/loopflow/infrastructure/intervention.py`：持久化 `source/options/allow_custom`，summary 返回 string response，新增 batch answer 校验，agent request id 纳入 call_id 防止并行覆盖。
- `src/loopflow/application/runner.py`：解析 `__loopflow.requests[]`，同一 Agent turn 可持久化多个 request；continue 恢复时把单 response 或 `responses[]` 回送同一 session。
- `src/loopflow/runtime.py`、`src/loopflow/presentation/cli.py`：`intervene()` 支持 options/custom，CLI run/resume 与 Web executor 注入一致，并把 intervention pending 标记为 `waiting_input`。
- `src/loopflow/application/web.py`、`src/loopflow/presentation/web/server.py`：新增 `POST /runs/{run_id}/interventions/responses`，保留旧单 request endpoint 兼容。
- `web/src/`：Intervention panel 改为多 pending request 表单，支持 options 选择与自定义字符串，一次 batch submit。
- `tests/recovery_support/manifest.py`、`tests/system/recovery_cases.json`：AC-023 planned 节点替换为真实测试节点。

# Next

0061 已完成，可进入下一步 SYSTEM_TEST 前置检查或新一轮设计讨论。

# Verification

- `pytest tests/unit/test_web_application.py tests/unit/test_runtime.py tests/unit/test_web_execution.py tests/integration/test_web_api.py tests/infrastructure/test_recovery_manifest.py tests/infrastructure/test_recovery_support.py -q`：144 passed
- `npm --prefix web run typecheck`：passed
- `npm --prefix web test -- --run`：15 passed
- `python3 scripts/check-ac-manifest.py --profile recovery`：55 scenarios
