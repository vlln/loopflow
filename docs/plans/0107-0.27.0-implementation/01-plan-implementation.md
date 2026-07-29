---
title: 0.27.0 契约实现
description: 以 TDD 实现 BL-046/051/052/054 并回填 AC-023、AC-033~035 manifest 节点
type: plan
status: pending
created: 2026-07-29T14:00:00Z
---

# Context

DESIGN 与 TEST_INFRA 已冻结并机器化 0.27.0 契约。当前 recovery 有 14 个、iteration027 有 29 个 `planned::` 节点，需要在同一单体应用分支中按共享依赖顺序实现。

# Request

1. 实现 BL-046 Agent 可发现 waiting_input 协议、schema 联合分支、capability preflight、分组持久化与并行 session 精确恢复。
2. 实现 BL-052 CLI/API/Web append_prompt，冻结 execution_options、参与 digest、recover 禁止覆盖。
3. 实现 BL-054 loop.md 顶层 args 优先、仅缺少 loop.md 时回退 workflow.py meta.args，并让 New Run 正确重建参数编辑器。
4. 闭环 BL-051 text/raw 大小、MIME、原子读取与 `file_read_failed` 语义。

# Output Format

- 产品实现、AC 对应单元/集成/前端契约测试。
- recovery/iteration027 manifest 全部替换为真实测试节点并 strict 通过。
- Report 逐项记录 AC 结果、commit、覆盖率与任何跳过原因。

# Constraints

- 不修改 active Spec/AC/Interface 或 accepted ADR。
- Agent control 与业务输出必须是互斥 schema 分支；unsupported 不静默 restart。
- Agent request 不接受 default/timeout；batch 必须恰好覆盖全部 pending requests且原子持久化。
- append_prompt 作为不受信任用户段，不进入 system prompt；UTF-8 最大 65536 bytes。
- raw 文件读取完成前不得发送 200 header；读取 OSError 映射 `file_read_failed`。
- 不放宽既有断言或覆盖率阈值。

# Checkpoint

- [ ] AC-023-N-6~F-5 全部真实节点并 strict recovery 通过
- [ ] AC-033 全部真实节点并 strict iteration027 通过
- [ ] AC-034 全部真实节点并 strict iteration027 通过
- [ ] AC-035 全部真实节点并 strict iteration027 通过
- [ ] Python/frontend MR 门禁通过
- [ ] subagent 独立审查无未解决 finding
- [ ] Report 完整并通过提测门禁

# Steps

1. 先写 BL-046 marshalling/runtime/intervention/recovery 红测，再实现并运行相关单元与契约测试。
2. 写 append_prompt CLI/API/Web 与 digest 红测，实现 execution_options 贯通。
3. 写 declared args discovery/Web/UI 红测，实现来源优先与编辑器重建。
4. 写 file preview OSError/边界/HTTP 原子响应红测，闭环错误映射。
5. 回填 manifest TEST_NODES，运行 strict profile、MR 门禁和独立审核。
6. 合并 develop，执行提测门禁并进入 SYSTEM_TEST。
