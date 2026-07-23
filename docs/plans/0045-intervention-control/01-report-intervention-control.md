---
title: Intervention Control Report
description: 记录 AC-022 人工介入实现、验证结果和剩余边界
type: report
status: complete
created: 2026-07-22T18:55:00Z
---

# Summary

实现 AC-022 阻塞人工介入。workflow 可通过 `intervene(key, prompt, schema=None)` 创建持久化 request 并让 Run 进入 `waiting_input`；用户回答后自动恢复同一 `run_id`，重放到相同 key/prompt/schema 时返回 response。Agent 只识别最终结构化 `__loopflow.status=waiting_input` 控制输出，且必须有 durable session 才能创建 `resume_mode=continue` request。Web API 和 WebUI 已支持 list/respond，重复回答、schema 错误、非 waiting Run 均按接口错误码处理。

# Acceptance

| 场景 | 结果 | 证据 | 提交 |
|------|------|------|------|
| AC-022-N-1 | [PASS] | `tests/unit/test_web_execution.py::test_workflow_intervention_waits_and_replays_answer` | `ef43bbb` |
| AC-022-N-2 | [PASS] | `tests/unit/test_web_application.py::test_intervention_response_validates_persists_and_recovers_same_run` | `ef43bbb` |
| AC-022-N-3 | [PASS] | `tests/unit/test_runtime.py::TestAgent::test_agent_structured_intervention_requires_durable_session` | `ef43bbb` |
| AC-022-N-4 | [PASS] | `web/src/App.test.tsx::answers a waiting intervention with a boolean control` | `ef43bbb` |
| AC-022-B-1 | [PASS] | `tests/integration/test_web_api.py::test_intervention_endpoints_list_validate_and_respond` | `ef43bbb` |
| AC-022-B-2 | [PASS] | `tests/unit/test_web_application.py::test_intervention_null_schema_accepts_any_json_value` | `ef43bbb` |
| AC-022-E-1 | [PASS] | `tests/unit/test_runtime.py::test_agent_natural_language_question_is_plain_output` | `ef43bbb` |
| AC-022-E-2 | [PASS] | `tests/unit/test_web_application.py::test_intervention_response_rejects_invalid_and_duplicate_without_recovery` | `ef43bbb` |
| AC-022-E-3 | [PASS] | `tests/unit/test_runtime.py::TestAgent::test_agent_intervention_without_durable_session_fails_without_request` | `ef43bbb` |
| AC-022-F-1 | [PASS] | `tests/unit/test_web_execution.py::test_workflow_intervention_replay_diverges_on_prompt_change` | `ef43bbb` |
| AC-022-F-2 | [PASS] | `tests/unit/test_runtime.py::TestAgent::test_agent_natural_language_question_is_plain_output` | `ef43bbb` |

# Checkpoints

| 检查点 | 结果 | 证据 |
|--------|------|------|
| Request storage | PASS | `run_dir/interventions/<request_id>.json` 原子写入 pending/answered，包含 digest、resume_mode、call/session identity 和事件 |
| Workflow replay | PASS | answered response 只在相同 key/prompt/schema 处注入；prompt 漂移写 `replay_diverged` |
| Agent continue | PASS | durable session 才创建 request；回答后以 continue recover 恢复目标 Call |
| API/UI | PASS | 新增 list/respond endpoint、错误映射、waiting_input respond action 和 boolean 控件 |
| Idempotency | PASS | 重复回答返回 `intervention_already_answered`，不覆盖 response，不启动第二个 worker |
| AC coverage | PASS | AC-022 11 个 manifest 节点均替换为真实测试；recovery strict manifest 通过 |
| Regression | PASS | AC-020/021 仍在 manifest；Python、frontend、browser、wheel 和 MR gate 均通过 |

# Verification

| 命令 | 结果 |
|------|------|
| `uv run pytest tests/unit/test_web_execution.py tests/unit/test_web_application.py tests/unit/test_runtime.py tests/integration/test_web_api.py -q` | PASS: 116 passed |
| `python3 scripts/check-ac-manifest.py --profile recovery` | PASS: 32 scenarios |
| `npm test -- --run` | PASS: 10 passed |
| `npm run typecheck` | PASS |
| `npm run build` | PASS |
| `npm run test:browser` | PASS: 10 passed, 2 skipped |
| `uv run pytest tests/ -q --cov=src/loopflow --cov-report=term` | PASS: 329 passed, 1 skipped; coverage 81.31% |
| `./scripts/mr-gate.sh` | PASS |

# Notes

- `request_id` 由 key 稳定派生；prompt/schema/resume_mode 通过 digest 校验 replay 是否漂移。
- workflow state 在顶层 workflow 成功终止时补充持久化，覆盖纯 `intervene()` 无 agent call 的场景。
- workflow loader 改为源码编译执行，避免测试或快速编辑同一路径 `workflow.py` 时命中字节码缓存旧内容。
- 首版 schema 校验只覆盖 AC 需要的简单 `type` 子集；复杂 JSON Schema 仍未实现。
