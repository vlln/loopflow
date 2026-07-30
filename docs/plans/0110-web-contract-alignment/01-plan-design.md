---
title: Web AgentGraph 契约对齐
description: 修复 ADR-0052 未传导到 Spec、Web AC、文件观察 AC 和 Web Interface 的设计缺陷
type: plan
status: done
created: 2026-07-29T00:00:00Z
---

# Context

0109 strict Web manifest 修复后，独立语义审查发现 active 契约仍要求已被 ADR-0052 删除的 PhaseGraph、phase occurrence、declared phases 和 phase_id；当前实现与测试明确使用 AgentGraph、call_id 和 label。AC-014-E-2 同时仍要求 stale 读取不修改 run.json，与 Spec BR-052 的首次记录 stale_since 冲突。

# Request

1. 将 Spec 升至 v19 proposed，完整传导 ADR-0052 的 Agent 实例图、事件、文件观察和 UI 语义。
2. 将 AC-0010、AC-0012 退回 proposed，保留场景编号与四维结构，改写被替代的 Phase oracle；修正 stale 场景。
3. 将 Web Interface 退回 proposed，按当前公开模型移除 Phase 字段并冻结 AgentGraph/FileChange 契约。
4. 为受影响 accepted ADR 增加 ADR-0052 优先级修订记录，并同步索引。
5. 按 Spec → AC/ADR → Interface 顺序做无编写上下文的独立 subagent 审查。

# Constraints

- 不恢复 `phase()`、`meta.phases`、`PhaseGraph`、`from_phase` 或 `only_phase`。
- 不修改 ADR-0052 的既有决策；本轮只补下游传导和冲突说明。
- 不因当前实现方便而削弱仍有效的 Runs/SSE/Loops/Backends/可访问性验收语义。
- 不编写业务代码或具体测试；缺口留给后续 TEST_INFRA/DEVELOP。
- proposed 文档只有在阶段末人类批量确认后才能统一 promote。

# Checkpoint

- [x] Spec v19 proposed 且独立审查通过
- [x] AC-0010/0012 proposed，四场景完整且独立审查通过
- [x] Web Interface proposed，字段/错误码与 Spec 一致且独立审查通过
- [x] 受影响 ADR 修订记录与索引一致
- [x] Report 汇总 0109 的 54 个 planned 场景如何被替代或保留
