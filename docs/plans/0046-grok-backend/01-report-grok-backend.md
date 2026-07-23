---
title: Grok Backend Report
description: 记录 Grok Build CLI 后端接入、streaming-json 解析和验证结果
type: report
status: complete
created: 2026-07-22T00:00:00Z
---

# Summary

已接入 Grok Build CLI backend。`grok` 后端使用 `grok -p <prompt> --output-format streaming-json --permission-mode bypassPermissions` 执行新 session，使用 `--resume <session_id>` 继续已有 session，并从 Grok `streaming-json` 的 `end.sessionId` 提取 durable session id。为用户误拼写保留 `gork` 兼容别名。

# Evidence

| 项 | 结果 | 证据 |
|----|------|------|
| CLI contract | [PASS] | `grok --help` 显示 `-p/--single`、`--output-format plain/json/streaming-json`、`--resume`、`--model`、`--system-prompt-override`；`grok --version` 返回 `grok 0.2.93 (f00f96316d4b)` |
| Grok docs | [PASS] | `~/GithubProjects/grok-build/crates/codegen/xai-grok-pager/docs/user-guide/14-headless-mode.md` 记录 `streaming-json` 事件：`text`、`thought`、`end`、`error`，`end` 携带 `sessionId` |
| Backend registration | [PASS] | `tests/unit/test_backend_refine.py::TestBaseBackend::test_cli_backends_declare_durable_resume[grok]` 和 `[gork]` |
| Stream parsing | [PASS] | `tests/unit/test_backend_refine.py::TestBaseBackend::test_grok_backend_parses_streaming_json` |
| Diagnostics list | [PASS] | `tests/unit/test_web_resources.py::test_backend_list_reports_missing_and_unknown_version` 覆盖 `BACKEND_META` 列表投影 |

# Acceptance

| 场景 | 结果 | 证据 | 提交 |
|------|------|------|------|
| AC-008-N-2 | [PASS] | `grok`/`gork` 注册到 backend manager，可显式选择且不影响已有后端 capability 测试 | `0e4741b` |
| AC-008-B-2 | [PASS] | 仅注册名可创建；未知 backend 仍由既有 `_make_backend` unknown 路径处理 | `0e4741b` |
| AC-008-E-1 | [PASS] | Grok 运行失败仍通过现有 `CliTransport` 返回 exit code；本 Plan 未改变错误处理路径 | `0e4741b` |

# Verification

| 命令 | 结果 |
|------|------|
| `.venv/bin/python -m pytest tests/unit/test_backend_refine.py tests/unit/test_web_resources.py -q` | PASS: 25 passed |
| `.venv/bin/python -m py_compile src/loopflow/infrastructure/backends/grok.py src/loopflow/infrastructure/backends/manager.py src/loopflow/infrastructure/backends/diagnostics.py` | PASS |
| `grok -p "Reply with exactly: loopflow-grok-ok" --output-format streaming-json --permission-mode bypassPermissions --disallowed-tools "run_terminal_cmd,grep,read_file,search_replace,list_dir,web_search,web_fetch,todo_write,task,Agent" --max-turns 1` | PASS: returned `loopflow-grok-ok`, `sessionId=019f8996-a796-7513-9206-a47911aa46f3` |
| `grok -p "Reply with exactly: loopflow-grok-adapter-ok" --output-format streaming-json --permission-mode bypassPermissions --max-turns 1` | PASS: returned `loopflow-grok-adapter-ok`, `sessionId=019f8997-25ab-7173-898e-956133b9c73c` |

# Notes

- 系统默认 `python3` 是 3.9.6，不满足项目 Python 3.10+ 语法；验证改用项目 `.venv` 的 Python。
- `uv run python --version` 在 sandbox 内因 `/Users/vlln/.cache/uv` 权限失败，未作为最终验证命令。
- 未运行 `scripts/submission-gate.py`：当前默认 system manifest 未收录 AC-008 场景，本 Report 以 docs/ac/0001-loopflow.md 的 AC-008 为契约来源。
- 已执行真实 Grok headless smoke。首次 sandbox 内调用因 Grok session/auth storage 权限失败，获准后在 sandbox 外完成；第二次 adapter 同形态命令可直接运行。未执行完整 loopflow workflow 端到端，避免让 Grok backend 在项目目录中获得不受 `--disallowed-tools` 限制的真实工具执行机会。
