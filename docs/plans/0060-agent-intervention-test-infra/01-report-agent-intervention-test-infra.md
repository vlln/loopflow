---
title: Agent Structured Intervention Test Infrastructure Report
description: 记录 Agent structured intervention vNext 测试契约同步结果
type: report
status: complete
created: 2026-07-23T18:00:00Z
---

# Summary

0060 已完成 TEST_INFRA 同步。Agent structured intervention vNext 现在有 AC-023、Web API interface vNext、recovery support contract schema、negative shape tests 和 planned manifest 节点。当前产品代码未修改，AC-023 的 16 个场景保持 `planned::`，strict manifest 会拦截未实现状态。

# Results

| 检查点 | 结果 | 证据 |
|--------|------|------|
| AC | PASS | 新增 AC-023-N/B/E/F 共 16 个场景 |
| Interface | PASS | 新增 InterventionSummary vNext 和 batch respond endpoint |
| Contract | PASS | 新增 `intervention_vnext` 与 `batch_intervention_response` schema/examples |
| Negative tests | PASS | 旧 intervention shape、schema 字段、非 string response、空 batch response 均被 vNext contract 拒绝 |
| Manifest | PASS | `tests/system/recovery_cases.json` 重新生成，55 scenarios |
| Planned gate | PASS | `python3 scripts/check-ac-manifest.py --profile recovery --allow-planned` 通过；strict checker 对 16 个 AC-023 planned nodes 失败，符合 DEVELOP 前状态 |
| Scope | PASS | 未修改 `src/` 产品实现或 Web 前端业务代码 |
| Tests | PASS | `pytest tests/infrastructure/test_recovery_support.py tests/infrastructure/test_recovery_manifest.py`：16 passed |

# Changes

- `docs/ac/0011-recovery-intervention.md`
  - 新增 AC-023，覆盖 Agent 多 requests、options/custom、batch respond all-or-nothing、workflow routing gate、CLI/Web intervene 注入一致性。
- `docs/interface/0001-web-api.md`
  - 新增 InterventionSummary vNext 字段。
  - 新增 `POST /runs/{run_id}/interventions/responses` vNext batch respond command。
- `tests/recovery_support/contracts.py`
  - 新增 vNext read model 和 batch body contract schema。
- `tests/infrastructure/test_recovery_support.py`
  - 新增 vNext contract 反向自证。
- `tests/recovery_support/manifest.py`
  - 新增 AC-023 targets/expectations。
- `tests/system/recovery_cases.json`
  - 由当前 AC 重新生成，新增 16 个 planned nodes。

# Next

进入 DEVELOP 后至少需要替换以下 planned 语义：

| 范围 | 语义 |
|------|------|
| Agent control output | `requests[]`、options/allow_custom 校验、单 turn 多 request |
| Intervention storage/read model | `source/options/allow_custom/response:string` |
| Respond command | batch all-or-nothing、一次恢复 worker |
| Runtime/CLI/Web executor | `intervene()` 注入一致，workflow routing gate |
| WebUI | 多问题表单、options/custom、一次提交 |
