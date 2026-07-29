---
title: Web manifest strict 基建修复 Report
description: 记录 Web manifest 真实节点 allowlist、自证结果以及暴露出的设计契约与覆盖缺口
type: report
status: complete
created: 2026-07-29T00:00:00Z
---

# Summary

0109 已修复 Web manifest 无条件生成 `planned::` 的基础设施缺陷。生成器现在为 28 个经语义审查完整覆盖的场景生成冻结真实节点，其他场景保持 planned；checker 在 strict 和 allow-planned 两种模式下均校验已映射节点精确一致且真实存在，未映射场景不能通过替换成任意现存节点绕过门禁。

增量 TEST_INFRA 自证通过，但“系统测试脚本对齐 AC”门禁未通过：strict 正确拒绝 54 个非 superseded 场景。三路 subagent 语义审查确认其中既有 active AC 与 ADR-0052/现行实现冲突，也有仍有效 AC 缺少完整自动化覆盖。因此 0109 作为失败执行单元关闭，流程应从 TEST_INFRA 转回 DESIGN 修订契约，而不是制造假绿后恢复 SYSTEM_TEST。

# Changes

| 层 | 内容 |
|----|------|
| Generator | `TEST_NODES` 仅登记 28 个完整覆盖场景；其余保留 planned |
| Checker | mapped 场景强制精确映射和文件/selector 存在；unmapped 场景仅在 allow-planned 下接受 planned |
| Committed manifest | `tests/system/cases.json` 由 generator 重建并由基础设施测试锁定一致性 |
| 正反例 | 拒绝 mapped→planned、映射漂移、未映射→任意现存节点、实现节点不存在 |

# Incremental Gate

| 检查项 | 结论 | 依据 / 证据路径 |
|--------|------|-----------------|
| Generator 与提交 manifest 一致 | PASS | `tests/infrastructure/test_ac_manifest.py::test_committed_manifest_matches_generator` |
| 真实节点存在性与 allowlist | PASS | 同文件 mapping drift、unmapped node、missing implemented node 三组反例 |
| 基础设施回归 | PASS | `uv run pytest tests/infrastructure/ -q`：81 passed、1 skipped |
| allow-planned 完整性 | PASS | `python3 scripts/check-ac-manifest.py --allow-planned`：86 scenarios |
| strict 正确拦截 | PASS | `python3 scripts/check-ac-manifest.py`：仅拒绝 54 个 planned 场景，无结构类附加错误 |
| 系统测试脚本对齐 AC | FAIL | 三路 subagent 逐场景语义审查；仅 28 个可完整映射，partial 节点未登记 |
| 独立最终复审 | PASS | `review_0109_infra` 第三次复审无 remaining findings |

# Failure Classification

| 类别 | 证据 | 处置 |
|------|------|------|
| 已修复基建缺陷 | 原 generator 对 86 场景无条件生成 planned，且不验证节点存在 | 0109 checker/generator 修复已通过正反向自证 |
| 设计契约缺陷 | AC-015 仍要求 Phase graph、occurrence、declared phases；accepted ADR-0052 与当前 API 明确删除这些模型。AC-014-E-2 要求只读不修改 run.json，而现行 stale 语义会首次记录 `stale_since` | 返回 DESIGN，修订 active Spec/AC 并重新审查冻结 |
| 测试/产品缺口 | AC-014、016~019 多个有效场景只有局部节点；代表项包括 SSE p95、Loop 删除后刷新、Backend 503、键盘路径、SSE 断线 UI | 契约对齐后进入 TEST_INFRA 生成 planned，再在 DEVELOP 补测试及必要产品修复 |

# Commits

- `d7d4ad7 test(web): enforce strict manifest node mappings`

# Next

1. 在 DESIGN 对齐 Spec v18、AC-0010 与 ADR-0052/stale 语义，明确 superseded 与替代 Agent graph 场景。
2. 对仍有效但未完整覆盖的 Web AC 保持业务语义，形成增量测试与实现 Plan。
3. 经人类确认重新冻结后，按 TEST_INFRA → DEVELOP → SYSTEM_TEST 恢复；0108 仍保持 pending，并从 Web strict 层重跑。
