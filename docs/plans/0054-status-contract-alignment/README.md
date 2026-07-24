# 0054 状态契约对齐

对应阶段：`DESIGN`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [状态契约对齐](01-plan-status-contract-alignment.md) | [Report](01-report-status-contract-alignment.md) | done |

## 背景

0.18.0 本地 RELEASE 后复核发现，状态语义主链路已经对齐，但 InterventionSummary 的活跃接口文档、recovery contract fixture 与产品实现存在字段漂移。

## 范围

- 对齐 InterventionSummary 的时间字段命名。
- 补齐接口已承诺的 `can_continue_session`。
- 清理仍表达“永久停止”的活跃文档索引 wording。
- 用契约检查和相关测试证明对齐结果。

## 非范围

- 不改变 Run 生命周期状态集合。
- 不重新设计取消恢复语义。
- 不发布新版本。
