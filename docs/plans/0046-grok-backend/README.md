# 0046 Grok Backend

对应分支：`feat/0046-grok-backend`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Grok 后端接入](01-plan-grok-backend.md) | [实现报告](01-report-grok-backend.md) | done |

## 范围

- 新增 `grok` CLI headless backend 适配
- 注册 `grok` 后端与 `gork` 拼写兼容别名
- 支持 streaming-json 文本、思考流和 durable session id 解析
- 更新后端诊断元数据、README 后端列表和单元测试
