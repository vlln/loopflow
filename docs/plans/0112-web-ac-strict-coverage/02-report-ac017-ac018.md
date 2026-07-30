---
title: AC-017/AC-018 覆盖报告
description: 0112-02 执行结果：16 个 planned 场景补齐为真实测试节点，strict 两段清零
type: report
status: complete
created: 2026-07-30T00:00:00Z
---

# Summary

AC-017（Loops 工作区）8 个与 AC-018（Backends 工作区）8 个 planned 场景全部补齐为真实测试节点。产品行为与冻结契约一致，未修改产品实现。strict 检查 AC-017/AC-018 段 0 planned（其余 AC-014/015/019 共 49 个 planned 属后续单元）。

# Acceptance Results

| AC | 测试节点 | 结果与提交 |
|----|----------|------------|
| AC-017-N-1 | `web/src/App.test.tsx::AC-017-N-1: selecting a Loop keeps both items and swaps detail in place` | [PASS] `501059d` |
| AC-017-N-2 | `tests/integration/test_web_api.py::test_ac017_n2_loop_file_previews_text_and_binary` | [PASS] `501059d` |
| AC-017-N-3 | `tests/integration/test_web_api.py::test_ac017_n3_run_file_changes_binary_preview` | [PASS] `501059d` |
| AC-017-B-1 | `web/src/App.test.tsx::AC-017-B-1: loop with no agents shows 0 Agents empty state without error` | [PASS] `501059d` |
| AC-017-B-2 | `tests/integration/test_web_api.py::test_ac017_b2_loop_preview_rejects_binary_oversized` | [PASS] `501059d` |
| AC-017-F-1 | `tests/integration/test_web_api.py::test_ac017_f1_loop_deleted_returns_404` | [PASS] `501059d` |
| AC-017-F-2 | `tests/integration/test_web_api.py::test_ac017_f2_invalid_yaml_marks_loop_invalid` | [PASS] `501059d` |
| AC-017-F-3 | `tests/integration/test_web_api.py::test_ac017_f3_loop_raw_read_failure_no_partial_headers` | [PASS] `501059d` |
| AC-018-N-1 | `tests/integration/test_web_api.py::test_ac018_n1_backends_list_real_fields` | [PASS] `501059d` |
| AC-018-N-2 | `tests/integration/test_web_api.py::test_ac018_n2_stderr_token_redacted` | [PASS] `501059d` |
| AC-018-B-1 | `tests/integration/test_web_api.py::test_ac018_b1_no_backends_empty_state` | [PASS] `501059d` |
| AC-018-B-2 | `tests/integration/test_web_api.py::test_ac018_b2_unknown_version_renders_null` | [PASS] `501059d` |
| AC-018-E-1 | `tests/integration/test_web_api.py::test_ac018_e1_diagnostic_timeout` | [PASS] `501059d` |
| AC-018-E-2 | `tests/integration/test_web_api.py::test_ac018_e2_invalid_encoding_uses_replacement` | [PASS] `501059d` |
| AC-018-F-1 | `tests/integration/test_web_api.py::test_ac018_f1_unknown_backend_404` | [PASS] `501059d` |
| AC-018-F-2 | `tests/integration/test_web_api.py::test_ac018_f2_diagnostic_start_failed_503` | [PASS] `501059d` |

# Verification

| 门禁 | 结果 |
|------|------|
| strict manifest（AC-017/018 段） | 0 planned；其余段 49 planned 不变 |
| infrastructure 回归 | 82 passed, 1 skipped |
| Web API 集成回归 | 76 passed |
| Frontend | 58 passed（含新增 5 个 UI 节点） |
| 产品实现改动 | 无（契约已符合） |

# 设计说明

- AC-018 后端诊断语义无独立 UI 单元节点：诊断面板是后端诊断结果的直接渲染，N-2（DOM 无明文 token）、B-1（空状态无健康百分比）、B-2（Unknown 版本）的 DOM 语义用 `web/src/App.test.tsx` 三个 UI 测试覆盖；对应 API 语义（脱敏、超时、替换字符、503、404）用 `tests/integration/test_web_api.py` 真实 runner 注入覆盖。两类节点分别映射，不重复登记。
- `_backend_app` 辅助函数为需要真实 `BackendRepository` 的诊断测试构建独立 server，每个测试用 `tmp_path / "be"` 隔离，避免与共享 `api` fixture 的 root 冲突。

# Acceptance Reasonableness

- F-3 断言响应为 JSON（非 200 + 部分 PNG bytes），且 body 不含 `\x89PNG` 魔数，覆盖"未先发送 200/部分字节"。
- N-2 同时断言 API stderr 无明文 token、含 `[REDACTED]` 与保留上下文，前端另断言 DOM 无 `lf-secret`。
- E-1 断言超时阈值 100ms 出现在 stderr 文案且 status=unavailable。
- N-1 断言列表含真实 status/cli_path/version/capabilities/transport 字段，1 available + 其余 missing。
- F-1 修正：初始用共享 `DiagnosticBackend` mock（对任意名字返回成功），改用真实 repo 后才暴露 404 语义——登记前跑红确认。
