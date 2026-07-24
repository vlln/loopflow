---
title: Hide Gork Backend Alias Report
description: 记录隐藏 gork backend 别名的修复结果
type: report
status: complete
created: 2026-07-24T02:04:18Z
---

# Summary

已删除由拼写错误引入的 `gork` backend 名称。`grok` 仍是唯一有效 Grok backend；`gork` 不再被 backend manager、diagnostics 或 WebUI backend list 接受。

# Results

- `src/loopflow/infrastructure/backends/manager.py` 移除 `gork -> GrokBackend` 注册。
- `src/loopflow/infrastructure/backends/diagnostics.py` 移除 `gork` metadata，因此自动检测、安装指南和 Web backend list 不再显示 `gork`。
- `tests/unit/test_backend_refine.py` 删除 `gork` durable backend 参数化用例，并新增 `_make_backend("gork")` unknown backend 断言。
- `tests/unit/test_backend_refine.py` 新增安装指南断言：列出 `grok`，不列出 `gork`，查询 `gork` 返回 unknown。
- `tests/unit/test_web_resources.py` 新增 Web backend list/diagnose 断言：`gork` 不出现在 list，diagnose `gork` 抛 `KeyError`。
- `docs/adr/0038-grok-backend-transport.md` 修订为：`grok` 是唯一后端名，`gork` 是错误拼写，不保留兼容。

# Verification

- `.venv/bin/python -m pytest tests/unit/test_backend_refine.py tests/unit/test_web_resources.py -q`：30 passed
- `.venv/bin/python -m pytest tests/integration/test_web_api.py -q`：11 passed
- `.venv/bin/python -m py_compile src/loopflow/infrastructure/backends/manager.py src/loopflow/infrastructure/backends/diagnostics.py src/loopflow/infrastructure/web_resources.py`：passed
- `git diff --check`：passed

说明：直接在 sandbox 内运行 integration Web API 测试时，本地 socket bind 被环境拒绝，报 `PermissionError: [Errno 1] Operation not permitted`。按工具规则提权后重跑同一测试通过。
