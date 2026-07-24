---
title: Cancel Recovery Implementation Plan
description: 实现 cancelled recover/respond、waiting_input stop 保留 pending request 和 atomic continue boundary
type: plan
status: done
created: 2026-07-23T13:05:00Z
---

# Goal

实现 0050 取消恢复语义，并把 0051 的 7 个 planned 节点替换为真实测试。

# Acceptance

1. waiting_input stop 后 Run 变为 cancelled，但 pending intervention request 保留。
2. cancelled Run 在存在恢复边界时允许 recover mode=retry。
3. active worker atomic/isolated 时 recover mode=continue 返回 `continue_not_supported`。
4. 非 atomic 且 durable session 可用时 cancelled recover mode=continue 可启动恢复。
5. cancelled + pending request 可 respond 并恢复同一 Run。
6. Run allowed_actions 与 WebUI 展示同步。
7. recovery manifest strict mode 不再有 planned 节点。

# Steps

1. 先修改单元/API/UI 测试，覆盖 7 个 planned 节点。
2. 更新 Run read model 的 allowed_actions 派生。
3. 更新 stop/recover/respond application command。
4. 更新 WebUI intervention 拉取和 Recover/Continue 按钮条件。
5. 重新生成 `tests/system/recovery_cases.json`，替换 planned nodes。
6. 跑 Python 相关测试、Web 单测和 manifest strict 校验。
7. 写 Report、标记 done 并提交。

# Checkpoints

| 检查点 | 通过条件 | 证据 |
|--------|----------|------|
| Stop | waiting_input stop 保留 pending request | Report |
| Recover | cancelled retry/continue 行为符合 AC | Report |
| Respond | cancelled pending request 可回答 | Report |
| UI | cancelled recover/respond controls 可见 | Report |
| Manifest | recovery manifest strict 0 planned | Report |
| Tests | 相关 Python/Web 测试通过 | Report |

# Exit

全部验收通过后进入 SYSTEM_TEST，恢复发布前认证链路。
