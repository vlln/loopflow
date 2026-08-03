---
title: BL-059 子进程级测试确定性
description: 修复 test_mock_acp_support 等子进程测试 CI 偶发 flaky（启动/时序竞态）
type: plan
status: pending
created: 2026-08-03T00:00:00Z
---

# Context

`test_mock_acp_support` 用子进程起 mock ACP server 的测试在 CI 偶发失败（本地 3 次全过，重跑即过），属子进程启动/时序竞态。CI 噪声会掩盖真实回归（0.27.1 事件串线先例）。

# Request

1. 定位 `test_mock_context_prefix_only_first_prompt` 等子进程测试的竞态窗口。
2. 让这类测试确定性：同步等待就绪信号替代 sleep、或缩短竞态窗口。
3. 本地重跑验证稳定性，CI 全绿。

# Constraints

- 不修改产品代码（`src/loopflow/`），仅测试基建层。
- 不改变测试语义与断言。
- 文档与测试代码分开提交。

# Checkpoint

- [ ] 竞态窗口定位并消除（无 sleep 等待 / 就绪信号同步）
- [ ] 本地连续 3 次全过
- [ ] CI 五 checks 全绿
