---
title: Web AgentGraph 契约对齐 Report
description: 记录 ADR-0052 向 Spec、AC、ADR 与 Web Interface 的传导、独立审查和 strict planned 场景处置
type: report
status: complete
created: 2026-07-29T00:00:00Z
---

# Summary

0110 已将 accepted ADR-0052 的 Agent 实例语义传导到全部受影响 Web 权威契约。Spec v19、AC-0010/0012、ADR-0033/0034/0041 修订和 Web Interface 均保持 proposed 并通过独立审查；ADR-0009 明确 superseded。现行契约不再公开 PhaseGraph、phase occurrence、declared_phases、from_phase 或 only_phase，以 call_id 唯一的 AgentGraph、label 显示名和 sequential/fork/join edge 为唯一图模型。

本执行单元只修订设计文档，未修改业务代码、测试或 manifest。当前提交等待 DESIGN 阶段末人类批量确认；确认后统一 promote，再进入 TEST_INFRA 重建 Web manifest。

# Contract Changes

| 文档 | 结论 |
|------|------|
| Spec v19 | AgentGraph/call_id/label 取代 Phase；首次 stale 读取记录 stale_since；RunDetail 明确 unattributed/malformed 互斥分类和 `{reason, raw}` 结构 |
| AC-0010 | AC-015 原编号改写为 AgentGraph/Call oracle；补 stale 宽限期、图片/PDF raw preview、读取失败和无 Phase UI surface 场景 |
| AC-0012 | 文件变化边界改为 Agent Call 完成，以 call_id/label 归属；缺文件只接受空状态 |
| ADR | ADR-0009 superseded；0033/0034/0041 保留仍有效技术决策并声明 ADR-0052 对历史 Phase 条款的优先级 |
| Interface | 删除 current_phase、iteration_count、graph、occurrences、phase_id、from_phase、only_phase、declared_phases；冻结 AgentGraph、MalformedEvent、FileChangeRecord、双 topic SSE 和 Intervention response 联合类型 |

# Independent Reviews

| 审查对象 | 结论 | 主要整改 |
|----------|------|----------|
| Spec v19 | PASS | 补模块 ownership/依赖方向、术语代码标识符、malformed/unattributed 投影；明确事件分类顺序与 Agent 关联类型集合 |
| AC-0010/0012 | PASS | 收紧 LR/no-Phase oracle、raw media type、args 权威、stale grace、空状态及 malformed `{reason, raw}` 断言 |
| ADR 传导 | PASS | 确认 0052 未修改，0009 状态与 0033/0034/0041 有效范围、索引一致 |
| Web Interface | PASS | 修正 malformed_count 口径；区分 file_changes cursor 的 topic 隔离与 reader I/O 失败的整连接关闭语义 |

# Original 54 Planned Scenarios

0109 的 committed manifest 含 58 个 planned 条目，其中 AC-014-N-3/N-5/N-6/F-1 已在 `SUPERSEDED_AC_IDS` 中排除；strict 实际拒绝的 54 个非 superseded 场景不通过伪造映射消除，处置如下：

| 类别 | 数量 | 场景 | 后续 |
|------|------|------|------|
| Oracle 被 AgentGraph 替代 | 17 | 0109 中 planned 的全部 AC-015 场景 | 保留原 ID 追踪；按新 AgentGraph/Call/malformed oracle 重新判定现有节点，未完整覆盖者保持 planned |
| 有效行为保留或收紧 | 37 | AC-014、016~019 的原 strict planned 场景 | 继续作为真实覆盖缺口；不得用 partial 节点通过 strict |

上述两类合计 54。另 4 个 superseded 条目继续由 `SUPERSEDED_AC_IDS` 排除，不生成测试债。

本轮另新增 AC-014-B-7、AC-017-N-3、AC-017-F-3，分别覆盖 stale 宽限期、Run 图片/PDF raw preview、raw 读取失败原子响应。TEST_INFRA 必须把三者加入 TARGETS/manifest。既有 28 个 TEST_NODES 也需按新 oracle 重新语义审查；场景文字变化导致当前 committed manifest 与 AC source 不一致是预期的设计传导结果，不在 DESIGN 阶段直接改测试基建。

# Gate Evidence

| 检查项 | 结论 | 依据 |
|--------|------|------|
| Spec proposed 且完整 | PASS | `docs/spec/0001-loopflow.md` v19；commits 094a6c9、ac5a671 |
| AC 四维、可观测、术语一致 | PASS | `docs/ac/0010-webui.md`、`docs/ac/0012-file-changes.md`；commit 6342864 |
| ADR 修订与索引一致 | PASS | `docs/adr/0009-phase-graph.md`、0033、0034、0041、README；commit d0b5ea1 |
| Interface 入参/出参/错误码完整 | PASS | `docs/interface/0001-web-api.md`、README；commit e67390f |
| 文档格式 | PASS | `git diff --check` 无错误 |
| 人类冻结确认 | PENDING | DESIGN 阶段末不可委托门禁，确认后统一 promote |

# Next

1. 人类批量确认 Spec v19、AC-0010/0012、ADR 修订和 Web Interface。
2. 统一 promote 并推进到 TEST_INFRA。
3. 重建 Web TARGETS、协议 expectations 和 TEST_NODES，生成诚实的 planned 缺口。
4. 在 DEVELOP 补测试及必要产品修复，然后从 SYSTEM_TEST 的 Web strict 失败层恢复。
