---
title: 0.27.0 契约实现报告
description: 记录 BL-046/051/052/054 实现、验收、独立审查和 DEVELOP 门禁结果
type: report
status: complete
created: 2026-07-29T14:46:22Z
---

# Summary

BL-046、BL-051、BL-052、BL-054 已按冻结契约实现。recovery 98 场景与 iteration027 29 场景 manifest 均无 `planned::`；实现提交为 `5976139`。

# Acceptance Results

| AC | 测试节点 | 结果与提交 |
|----|----------|------------|
| AC-023-N-6 | `tests/unit/test_agent_intervention.py::test_agent_intervention_prompt_is_capability_gated` | [PASS] `5976139` |
| AC-023-N-7 | `tests/unit/test_agent_intervention.py::test_control_branch_bypasses_required_business_schema` | [PASS] `5976139` |
| AC-023-N-8 | `tests/unit/test_agent_intervention.py::test_answer_envelope_preserves_group_order_and_hides_internal_fields` | [PASS] `5976139` |
| AC-023-N-9 | `tests/unit/test_agent_intervention.py::test_parallel_agent_groups_batch_and_resume_their_own_sessions` | [PASS] `5976139` |
| AC-023-B-4 | `tests/unit/test_agent_intervention.py::test_agent_intervention_prompt_is_capability_gated` | [PASS] `5976139` |
| AC-023-B-5 | `tests/unit/test_agent_intervention.py::test_goal_mode_control_branch_is_prioritized_over_goal_schema` | [PASS] `5976139` |
| AC-023-B-6 | `tests/unit/test_agent_intervention.py::test_legacy_agent_requests_derive_stable_group_without_rewrite` | [PASS] `5976139` |
| AC-023-E-6 | `tests/unit/test_agent_intervention.py::test_reserved_business_field_fails_before_backend_call` | [PASS] `5976139` |
| AC-023-E-7 | `tests/unit/test_agent_intervention.py::test_invalid_control_is_rejected_before_any_request_is_written` | [PASS] `5976139` |
| AC-023-E-8 | `tests/unit/test_web_application.py::test_batch_must_exactly_cover_current_pending_requests` | [PASS] `5976139` |
| AC-023-E-9 | `tests/unit/test_agent_intervention.py::test_invalid_control_is_rejected_before_any_request_is_written` | [PASS] `5976139` |
| AC-023-E-10 | `tests/unit/test_agent_intervention.py::test_invalid_control_is_rejected_before_any_request_is_written` | [PASS] `5976139` |
| AC-023-F-4 | `tests/unit/test_agent_intervention.py::test_unsupported_backend_does_not_advertise_or_persist_control` | [PASS] `5976139` |
| AC-023-F-5 | `tests/unit/test_web_execution.py::test_recovery_fails_when_workflow_ends_before_all_continue_targets` | [PASS] `5976139` |
| AC-033-N-1 | `tests/integration/test_web_api.py::test_ac033_run_raw_preview_uses_fixed_media_types_and_headers` | [PASS] `5976139` |
| AC-033-N-2 | `web/src/App.test.tsx` Loop PDF raw-viewer scenario | [PASS] `5976139` |
| AC-033-N-3 | `web/tests/webui.spec.ts` image viewport/file-tree-layout scenario | [PASS] `5976139` |
| AC-033-B-1 | `tests/unit/test_web_resources.py::test_ac033_loop_preview_accepts_exact_text_and_raw_limits` | [PASS] `5976139` |
| AC-033-B-2 | `tests/integration/test_web_api.py::test_run_file_preview_rejects_binary_and_oversized` | [PASS] `5976139` |
| AC-033-B-3 | `tests/integration/test_web_api.py::test_run_file_preview_returns_text_content` | [PASS] `5976139` |
| AC-033-B-4 | `tests/integration/test_web_api.py::test_run_file_preview_rejects_binary_and_oversized` | [PASS] `5976139` |
| AC-033-E-1 | `tests/integration/test_web_api.py::test_ac033_raw_rejects_non_whitelisted_oversized_and_escaped_paths` | [PASS] `5976139` |
| AC-033-E-2 | `web/src/App.test.tsx` raw media failure replacement scenario | [PASS] `5976139` |
| AC-033-F-1 | `tests/unit/test_web_resources.py::test_ac033_loop_preview_binary_rejects_oversized` | [PASS] `5976139` |
| AC-033-F-2 | `tests/integration/test_web_api.py::test_ac033_raw_reader_failure_returns_file_error_before_success_headers` | [PASS] `5976139` |
| AC-034-N-1 | `tests/integration/test_cli.py::TestCLIRun::test_ac034_n1_cli_persists_and_appends_to_every_workflow_agent` | [PASS] `5976139` |
| AC-034-N-2 | `tests/integration/test_web_api.py::test_ac034_n2_http_value_reaches_workflow_agent_prompt` | [PASS] `5976139` |
| AC-034-N-3 | `tests/integration/test_cli.py::TestSingleAgentRun::test_ac034_n3_single_agent_forwards_append_prompt` | [PASS] `5976139` |
| AC-034-B-1 | `tests/unit/test_runtime.py::TestAgent::test_ac034_b1_empty_append_prompt_injects_no_empty_tags` | [PASS] `5976139` |
| AC-034-B-2 | `tests/integration/test_cli.py::TestSingleAgentRun::test_ac034_b2_e1_cli_validates_utf8_limit_before_run_creation` | [PASS] `5976139` |
| AC-034-E-1 | `tests/integration/test_cli.py::TestSingleAgentRun::test_ac034_b2_e1_cli_validates_utf8_limit_before_run_creation` | [PASS] `5976139` |
| AC-034-E-2 | `tests/unit/test_web_application.py::test_ac034_e2_recover_rejects_append_prompt_without_starting_worker` | [PASS] `5976139` |
| AC-034-E-3 | `tests/integration/test_web_api.py::test_ac034_n2_b2_e3_run_create_append_prompt_http_contract` | [PASS] `5976139` |
| AC-034-E-4 | `web/src/App.test.tsx` oversized UTF-8 append prompt scenario | [PASS] `5976139` |
| AC-034-F-1 | `tests/unit/test_runtime.py::TestAgent::test_ac034_f1_append_prompt_tamper_diverges_before_cache_hit` | [PASS] `5976139` |
| AC-034-F-2 | `tests/unit/test_runtime.py::TestAgent::test_ac034_n1_f2_append_prompt_is_last_user_segment_only` | [PASS] `5976139` |
| AC-035-N-1 | `web/src/App.test.tsx` declared args prefill/editor submit scenario | [PASS] `5976139` |
| AC-035-N-2 | `web/src/App.test.tsx` Editor/JSON preservation scenario | [PASS] `5976139` |
| AC-035-B-1 | `web/src/App.test.tsx` no-declared-args blank editor scenario | [PASS] `5976139` |
| AC-035-B-2 | `web/src/App.test.tsx` typed declared-defaults scenario | [PASS] `5976139` |
| AC-035-E-1 | `web/src/App.test.tsx` malformed declarations filtering scenario | [PASS] `5976139` |
| AC-035-E-2 | `tests/unit/test_web_resources.py::test_ac035_loop_md_top_level_args_and_legacy_workflow_fallback` | [PASS] `5976139` |
| AC-035-F-1 | `web/src/App.test.tsx` loop loading failure scenario | [PASS] `5976139` |

# Verification

| 门禁 | 结果 |
|------|------|
| Python MR 层 | 637 passed, 1 skipped；coverage 83.06% |
| Frontend | 52 passed；statements 87.46%、branches 81.06%、functions 83.45%、lines 94.62% |
| Browser | 16 passed, 2 viewport-independent skips；AC-033-N-3 三视口通过 |
| Manifest | web 86、recovery 98、scheduling 32、agent 26、singleagent 9、iteration027 29 |
| Build/security/wheel | TypeScript、Vite、npm audit（0 vulnerabilities）、wheel smoke 全部通过 |
| 独立审查 | AC、ADR-0057、Spec v18 三路 subagent 最终 PASS |

# Acceptance Reasonableness

- PASS 场景均可反向定位到上表测试节点与实现提交；测试断言覆盖返回值、持久化、副作用、HTTP/DOM/真实布局，而非仅“不抛异常”。
- 无失败场景或静默跳过；两个 Playwright skip 仅把 1000 Run 边界固定在 1440 视口，与本轮 AC 无关。
- 实现 diff 覆盖 runtime、recovery、Web API/resource、CLI 与 WebUI，和四项 backlog 的声明范围相称。
- 多文件持久化在正常及可恢复单点故障下提供补偿事务；若持续物理存储故障令补偿写本身失败，系统显式返回 `atomic_write_failed`，不会伪报成功。独立 JSON 文件无法在不可写介质上提供绝对物理原子性，此限制已通过 rollback-failure 故障注入固定。
