# 0047 Grok ACP Transport

对应分支：`feat/0047-grok-acp`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Grok ACP 接入](01-plan-grok-acp.md) | [实现报告](01-report-grok-acp.md) | done |

## 范围

- 为 Grok backend 增加显式 `transport="acp"` 路径
- 使用 `grok agent stdio` 作为 ACP stdio server
- 保持默认 Grok backend 继续走已验证的 CLI headless 模式
- 兼容 Grok ACP `_meta.rules` / `_meta.systemPromptOverride`
- 解析 Grok ACP `agent_message_chunk` 与 `agent_thought_chunk`
- 修正通用 ACP 初始化重复发送 `initialize` 的问题
