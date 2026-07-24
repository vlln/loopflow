# 0067 Hide Gork Backend Alias

对应阶段：`DEVELOP`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [隐藏 gork backend 别名](01-plan-hide-gork-backend-alias.md) | [Report](01-report-hide-gork-backend-alias.md) | pending |

## 背景

后端检测会同时返回 `grok` 和 `gork`。`gork` 是 0046 中为误拼写保留的兼容别名，但 diagnostics/WebUI 将其作为独立 backend 暴露，导致用户看到两个指向同一个 `grok` binary 的后端。

## 范围

- `grok` 保持唯一公开 backend 名称。
- `gork` 不出现在自动检测、WebUI backend 列表和安装指南中。
- 是否保留 `_make_backend("gork")` 兼容由实现保持最小风险。
