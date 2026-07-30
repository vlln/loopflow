---
title: Web AgentGraph manifest 增量基建 Report
description: 记录 Web manifest 的 AgentGraph target、完整测试节点复核和 strict planned 缺口自证
type: report
status: complete
created: 2026-07-29T00:00:00Z
---

# Summary

0111 已将 Web manifest 对齐冻结后的 89 个 AC-014~019 场景。Generator 不再使用 `ui:phase`，新增 AgentGraph、stale grace、Run/Loop raw preview 与 file changes targets，并将 `run_in_grace` 纳入 Interface error code 校验。

三路 subagent 逐场景审查现有测试后，TEST_NODES 从冻结前 28 个收缩为 14 个完整映射。其余 partial 节点全部降回 planned；strict 现在只拒绝 71 个真实覆盖缺口，不含 source drift、target drift、缺失 ID、伪造节点或其他结构错误。

# Changes

| 层 | 内容 |
|----|------|
| TARGETS | Phase UI 改为 `ui:agent-graph`；补 Loop+Run 查询、POST Run、file-changes、preview/raw endpoints |
| Protocol | 新增 `run_in_grace=409`、raw preview 200、`file_read_failed=500` expectations |
| TEST_NODES | 精确冻结 14 个完整节点；移除 15 个 partial 旧映射，新增 AC-016-N-2 的完整 cursor 节点 |
| Generator output | `tests/system/cases.json` 从 86 更新为 89 场景 |
| Self-proof | 基础设施测试锁定精确映射字典、71 planned、4 superseded、集合互斥和总数 89 |

# Mapping Review

| 范围 | 结论 |
|------|------|
| AC-014/017 | 保留 7 个；移除 rerun、declared args authority、unreadable repository 等 4 个 partial；新增场景均保持 planned |
| AC-015 | 只保留 incomplete final line；Call list、legacy UI 和 syntax-error API 节点均缺部分 UI/图 oracle |
| AC-016/018/019 | 保留 7 个完整 SSE 节点并新增 N-2 cursor 映射；移除 reducer 和 4 个不完整视觉/可访问性映射；Backend 场景保持 planned |
| 最终复审 | 首轮发现 2 个高估节点、3 处 target 漏项和映射集合未精确冻结；整改后 PASS |

# Incremental Gate

| 检查项 | 结论 | 依据 |
|--------|------|------|
| 既有测试基建 ADR 适用 | PASS | ADR-0035 的 Web component/Playwright/manifest 分层仍覆盖本轮；无新技术选型，不新增 ADR |
| Generator 与 committed manifest 一致 | PASS | `test_committed_manifest_matches_generator` |
| 89 个 frozen 场景完整 | PASS | `--write --allow-planned` 输出 `AC manifest ok: 89 scenarios` |
| 完整节点精确冻结 | PASS | `EXPECTED_TEST_NODES` 精确等于 14 个审查通过映射 |
| strict 正确拦截 | PASS | 89 total = 14 implemented + 71 planned + 4 superseded；strict errors=71 planned、other=0 |
| 增量 focused tests | PASS | `uv run pytest tests/infrastructure/test_ac_manifest.py -q`：8 passed |
| infrastructure 回归 | PASS | `uv run pytest tests/infrastructure/ -q`：82 passed、1 skipped；后续仅收紧映射并以 focused test 复验 |
| CI/MR/覆盖率/Mock | N/A | 本轮未修改这些既有组件，不重复其已通过自证 |
| 独立 subagent 审查 | PASS | 三路语义映射审查 + 最终整改复核，无 remaining findings |

# Commits

- `e96d8ef test(web): align manifest with AgentGraph contracts`

# Next

1. 合并 0111 到 develop，推进到 DEVELOP。
2. 以 71 个 planned 场景为测试清单，按产品边界拆分最小实现 Plan。
3. 补齐完整测试及必要产品修复后，将 TEST_NODES 更新为真实节点并通过 MR 门禁。
4. 恢复 SYSTEM_TEST 时只从 Web strict 失败层继续，不重复已通过的集成、CLI E2E 和其他 strict profiles。
