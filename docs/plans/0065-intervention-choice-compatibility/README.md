# 0065 Intervention Choice 兼容修复

对应阶段：`DEVELOP`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Boolean schema choice 兼容修复](01-plan-boolean-choice-compatibility.md) | [Report](01-report-boolean-choice-compatibility.md) | done |

## 背景

0.19.0 发布后，手工测试 `manual-approval` 发现旧 `intervene(schema={"type":"boolean"})` 只显示自定义输入框，没有显示 choices。

## 范围

- 旧 boolean schema request 在 vNext read model 中暴露 `["true", "false"]`。
- 提交 `"true"`/`"false"` 后，旧 workflow replay 仍获得 boolean。
- 增加后端回归测试。
