---
title: AC-016 SSE 事件流覆盖报告
description: 0112-01 执行结果：6 个 planned 场景补齐为真实测试节点，strict AC-016 段清零
type: report
status: complete
created: 2026-07-30T00:00:00Z
---

# Summary

AC-016 的 6 个 `planned::` 场景全部补齐为真实测试节点。产品行为与冻结契约一致，未修改产品实现。strict 检查 AC-016 段 0 planned（其余段 65 个 planned 保持不变，属后续单元）。

# Acceptance Results

| AC | 测试节点 | 结果与提交 |
|----|----------|------------|
| AC-016-N-1 | `tests/integration/test_web_api.py::test_ac016_n1_sse_replay_then_live_push` | [PASS] `c771879` |
| AC-016-B-1 | `tests/integration/test_web_api.py::test_ac016_b1_sse_end_cursor_streams_end_without_replay` | [PASS] `c771879` |
| AC-016-B-2 | `tests/integration/test_web_api.py::test_ac016_b2_sse_replay_latency_under_500ms` | [PASS] `c771879` |
| AC-016-E-1 | `tests/integration/test_web_api.py::test_ac016_e1_sse_cursor_out_of_range_returns_410` | [PASS] `c771879` |
| AC-016-E-2 | `web/src/eventReducer.test.ts::AC-016-E-2: applying the same event_id twice changes state only once` | [PASS] `c771879` |
| AC-016-F-1 | `tests/integration/test_web_api.py::test_ac016_f1_sse_unknown_run_returns_404` | [PASS] `c771879` |

# Verification

| 门禁 | 结果 |
|------|------|
| strict manifest（AC-016 段） | 0 planned；其余段 65 planned 不变 |
| infrastructure 回归 | 82 passed, 1 skipped |
| Web API 集成回归 | 62 passed |
| Frontend | 53 passed（含新增 E-2） |
| 产品实现改动 | 无（契约已符合） |

# 工程发现（测试基建）

N-1 场景需要"重放期间连接保持、新事件实时推送"的增量读取。排查发现两个测试基建缺陷并修复（随 `c771879` 提交）：

1. `tests/web_support/http.py` 新增 `split_sse_buffer`：SSE 帧以空行分帧，而 `parse_sse` 仅在遇到空行时提交事件——直接喂增量 chunk 会丢弃所有不完整帧。新函数按空行切帧、给帧补终止空行后复用 `parse_sse`。
2. `http.client.HTTPResponse.read1/readlines` 在 pytest 环境下对长连接 SSE 流会缓冲不放行（原始 socket 同一请求数据立即可达）。N-1 改用原始 socket 逐 chunk 读取，避免假阴性超时。

# Acceptance Reasonableness

- N-1 断言重放 id 序列 1..10 完整、随后新事件 11 实时到达、终态 stream_end，覆盖"重放 + 保持 + 推送"完整 oracle。
- B-2 断言 100 条 1KB 事件 id 严格递增且写→可读全程远低于 AC 的 500ms 上限，未放宽阈值。
- E-1/F-1 断言精确错误码与 details（max_event_id=10 / run_not_found），非仅状态码。
- E-2 断言 reducer 对重复 event_id 返回原状态引用（`toBe`），且后续事件仍正常应用，覆盖"只应用一次，不重复增加"。
