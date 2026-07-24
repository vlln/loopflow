---
title: Intervention Respond Test Infrastructure Report
description: 记录 respond 前置条件错误边界的 AC、接口契约、测试和 manifest 同步结果
type: report
status: complete
created: 2026-07-23T16:30:00Z
---

# Summary

0057 已完成 TEST_INFRA 同步。`respond` 的四类前置条件失败现在在 AC、Interface、application contract tests 和 recovery manifest 中都有明确证据：schema validation、request not found、already answered、invalid run transition。

# Results

| 检查点 | 结果 | 证据 |
|--------|------|------|
| AC | PASS | AC-022 新增 E-4/E-5；E-1/E-2/E-4/E-5 覆盖四类 respond 前置条件错误 |
| Interface | PASS | `POST /runs/{run_id}/interventions/{request_id}/response` 明确四类错误的无副作用边界 |
| Application contract tests | PASS | 新增/拆分 4 个 respond 错误边界测试，均断言不启动 executor 且不发生错误副作用 |
| Recovery manifest | PASS | `tests/system/recovery_cases.json` 重新生成，39 scenarios |
| Scope | PASS | 未修改 `src/` 产品实现或 Web 前端业务代码 |
| Tests | PASS | `pytest tests/unit/test_web_application.py tests/infrastructure/test_recovery_manifest.py`：27 passed |
| Manifest checker | PASS | `python3 scripts/check-ac-manifest.py --profile recovery`：39 scenarios；`--allow-planned` 同样通过 |

# Changes

- `docs/ac/0011-recovery-intervention.md`
  - 新增 AC-022-E-4 request not found。
  - 新增 AC-022-E-5 invalid run transition with pending request。
- `docs/interface/0001-web-api.md`
  - 补充 respond 前置条件错误与副作用边界。
  - 明确 response 持久化成功后的 worker/agent 失败属于普通 Run execution failure。
- `tests/unit/test_web_application.py`
  - 拆分 schema validation 和 duplicate answer 测试。
  - 新增 request not found 和 invalid run transition 无副作用测试。
- `tests/recovery_support/manifest.py`
  - 补新增 AC 的 target、expectation、test_node 映射。
- `tests/system/recovery_cases.json`
  - 由当前 AC 重新生成。

# Next

进入 DEVELOP，依据 0056/0057 调整 WebUI 展示层级和用户回答问题交互；产品实现不得削弱本轮固化的 respond command 边界。
