---
title: Workflow Kwargs Compatibility Fix Report
description: 记录 workflow kwargs 兼容与 contract example 修复结果
type: report
status: complete
created: 2026-07-23T19:35:00Z
---

# Summary

已修复 0062 SYSTEM_TEST MR gate 暴露的局部 bug。新增共享 helper 按 workflow `run()` 签名过滤框架注入 kwargs；严格签名 workflow 不再收到未知 `intervene` 参数，声明 `intervene` 或 `**kwargs` 的 workflow 仍可获得该能力。同步修复 Web contract example 的 vNext InterventionSummary shape。

# Results

- 新增 `src/loopflow/infrastructure/workflow_args.py::accepted_kwargs()`。
- `src/loopflow/presentation/cli.py`、`src/loopflow/application/execution.py`、`src/loopflow/runtime.py` 调用 workflow 前统一使用签名过滤。
- `tests/web_support/contracts.py::contract_examples()` 改为 `source/options/allow_custom/response:string` 口径。

# Verification

- `pytest tests/e2e/test_graph_e2e.py tests/infrastructure/test_web_test_support.py -q`：13 passed
- `pytest tests/unit/test_web_execution.py tests/unit/test_runtime.py tests/unit/test_web_application.py tests/integration/test_web_api.py -q`：128 passed
- `npm --prefix web run typecheck`：passed
- `npm --prefix web test -- --run`：15 passed
