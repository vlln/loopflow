---
title: BL-059 子进程级测试确定性 — Report
description: test_mock_acp_support 子进程测试 flaky 修复记录
type: report
status: complete
created: 2026-08-03T00:00:00Z
---

# Report — BL-059 子进程测试确定性

## 结论

已修复。竞态窗口定位为「`conn.prompt()` 返回时 `session_update` 通知尚未异步投递到 collector」——SDK 的 prompt 响应与通知分发是独立通道，测试立即提取 `collector.updates` 断言导致偶发缺 `[context]`（CI develop run 30546040994 实证：`test_mock_context_prefix_only_first_prompt` FAILED，`assert any("[context]" in t for t in first_texts)`）。

## 修复

`tests/infrastructure/test_mock_acp_support.py`：
- 新增 `_wait_more_updates(collector, before)`：轮询等待（5s 超时，10ms 间隔）collector 收到超过基准数的通知，替代对通知时序的隐式假设。
- `_drive()` 每个 prompt 后与 `test_mock_context_prefix_only_first_prompt` 两次 prompt 后均加确定性等待。
- 未使用固定 sleep（BL-059 建议「同步等待就绪信号替代 sleep」），未改测试语义与断言。

## 自证

| 项 | 结果 | 证据 |
|----|------|------|
| 本地连续 5 次 | 12 passed × 5 | 修改后本地 5 轮全过 |
| 全量单测/基建 | 521 passed, 1 skipped | `tests/unit tests/infrastructure` |
| MR 门禁 | 全绿 | 693 Python + 65 前端 + 16 Playwright，覆盖率 83.45% |
| CI | 待 PR 触发 | PR #36 后五 checks 全绿 |

## 证据路径

- commit `b049271`（test/infra）
- CI 失败基线：develop run `30546040994` `test_mock_context_prefix_only_first_prompt FAILED`
