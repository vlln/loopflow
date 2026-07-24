# 0063 SYSTEM_TEST 局部修复

对应阶段：`DEVELOP`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Workflow kwargs 兼容修复](01-plan-workflow-kwargs-fix.md) | [Report](01-report-workflow-kwargs-fix.md) | done |

## 背景

0062 SYSTEM_TEST 的 MR gate 在 Python 全量阶段失败。失败分类为局部 bug：

- CLI 注入 `intervene` 后，严格签名 workflow 收到未知 kwargs。
- Web contract example 未同步 vNext intervention shape。

## 范围

- 修复 workflow 调用 kwargs 与函数签名兼容。
- 同步 contract example。
- 运行失败相关测试与门禁。
