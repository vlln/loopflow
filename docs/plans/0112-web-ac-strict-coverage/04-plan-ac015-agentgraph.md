---
title: AC-015 AgentGraph 覆盖补齐
description: 为 AC-015 的 21 个 planned 场景编写真实测试节点，必要时补产品行为
type: plan
status: pending
created: 2026-07-30T00:00:00Z
---

# Context

AC-015（AgentGraph 与 Agent Call 运行过程，ADR-0052 后 oracle 统一为 call_id 唯一节点）planned 21 个：N-1（3 节点 2 序边 current=call-3 + dagre LR 截图）、N-2（节点选择联动 Events/文件变化高亮）、N-3（fork/join 并行图）、N-4（back-to-back fork/join + current 只标记当前）、N-5（Inspector state + Call 详情不伪造 state diff）、N-6（空 agent_graph 不含 declared_phases）、N-7（运行中新增节点标 running/current）、N-8（同 label 双节点不合并）、N-9（call-list 主显 call_id、session_id 仅 tooltip）、B-1（无 Agent 事件空状态）、B-2（100 顺序 Call 可选中首尾）、B-3（无 declared_phases 泄漏）、B-4（单节点无 edge 无 Phase 控件）、B-5（缺 session_id 不渲染空白行）、E-1（legacy 歧义事件 unattributed）、E-2（missing_call_id → malformed 数组精确语义）、E-3（label 空 → call_id fallback）、E-4（节点数/选中/事件数准确不混 occurrence 术语）、F-1（events.jsonl 不存在 → 200 空集合不 500）、F-3（workflow.py 语法错误 → 500 internal_error 不建 Run）、F-4（legacy 事件不进任何 Call）。已登记：F-2。分支 `feat/0112-ac015-agentgraph`。

# Request

1. 为 21 个场景各写真实测试节点：API 语义（N-6/E-2/F-1/F-3、B-3 响应字段、E-1 unattributed、N-5 Inspector 数据）用 `tests/integration/test_web_api.py` / `tests/unit/`，图结构与 UI 语义（N-1~N-4/N-7~N-9/B-1/B-2/B-4/B-5/E-3/E-4/F-4）用 `web/src/App.test.tsx`；标注"自动化 + 截图"的 N-1/N-4/N-8 布局断言可用 jsdom 结构断言 + 现有 Playwright 截图用例覆盖，若现有截图用例不足以覆盖 oracle 则在 `web/tests/webui.spec.ts` 追加。
2. TDD 先红后绿；产品行为不符冻结契约时补最小实现。预期主要缺口在：unattributed 标记、malformed 精确语义、call-list session tooltip、同 label 不合并等，实现前先跑红确认。
3. `TEST_NODES` 仅追加 AC-015 段，重新生成 `cases.json`。
4. 验证 strict 下 AC-015 段 0 planned。

# Constraints

- 不改契约文档；契约存疑停下来上报。
- E-2 必须断言 malformed/malformed_count 精确等于 1 且 raw 不出现在任何合法集合——这是 0110 重点修复语义，不得弱化。
- N-8 必须断言同 label 两个独立节点存在且不出现 occurrence 概念。
- 截图类场景不放宽为"不崩溃"，必须断言布局 oracle（LR 排列、edge 方向、current 唯一）。
- 只追加 `TEST_NODES` 本段条目；文档与代码分开提交；commit 标注 AC 编号。

# Checkpoint

- [ ] 21 个测试节点有实质断言
- [ ] MR 门禁通过
- [ ] strict 检查 AC-015 段清零
- [ ] Report 留档，可反向定位
