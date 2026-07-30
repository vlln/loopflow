---
title: AC-016 SSE 事件流覆盖补齐
description: 为 AC-016 的 6 个 planned 场景编写真实测试节点，必要时补产品行为
type: plan
status: pending
created: 2026-07-30T00:00:00Z
---

# Context

0111 冻结的 Web manifest 中 AC-016 有 6 个 `planned::` 节点：N-1（无游标重放 1..10 后推送新事件）、B-1（已结束 Run 以 last_event_id=10 订阅 → stream_end 含 last_event_id）、B-2（100 条事件 p95 落盘到可读延迟 < 500ms）、E-1（last_event_id 超出 → 410 cursor_out_of_range 含 max_event_id）、E-2（前端 reducer 去重）、F-1（run_id 不存在 → 404 不重试）。既有 7 个 AC-016 节点已实现（N-2/N-3/N-4/B-3/E-3/F-2/F-3），测试模式可复用 `tests/integration/test_web_api.py` 中既有 SSE 用例。分支 `feat/0112-ac016-sse`。

# Request

1. 按 AC-0010 文档 AC-016 节语义，为上述 6 个场景各写一个真实测试节点：N-1/B-1/B-2/E-1/F-1 为后端 SSE 集成测试（`tests/integration/test_web_api.py`），E-2 为前端事件 reducer 测试（`web/src/`，manifest target 为 `ui:event-reducer`）。
2. TDD：先写测试跑红，若产品行为已符合则直接转绿；不符合时补最小产品改动使其符合冻结契约。
3. 将 6 个映射追加到 `tests/web_support/ac_manifest.py` 的 `TEST_NODES`（仅 AC-016 段），重新生成 `tests/system/cases.json`。
4. 验证 strict 模式下 AC-016 段 0 planned，其余段 planned 数不变（65）。

# Constraints

- 不修改 active Spec/AC/Interface 或 accepted ADR；测试揭露契约与实现不符且实现明显错误时修实现，契约本身存疑则停下来上报，不改契约文档。
- 只追加 `TEST_NODES` 的 AC-016 条目，不动其他 AC 段；`cases.json` 由 generator 重新生成。
- B-2 性能断言按 AC 固定 p95 < 500ms，不得放宽阈值迁就实现。
- 文档与代码分开提交；commit 信息标注 AC 编号（如 `test(web): AC-016-N-1 SSE replay`）。

# Checkpoint

- [ ] 6 个场景测试节点存在且有实质断言（事件序列/游标语义/错误码/延迟，而非"不抛异常"）
- [ ] MR 门禁通过（Python 层 + frontend + browser 不回归）
- [ ] strict 检查 AC-016 段清零，其余段 planned 计数不变
- [ ] Report 留档，验收结果可反向定位到 commit
