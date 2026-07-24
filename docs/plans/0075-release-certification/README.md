# 0075 RELEASE 认证（0.20.0）

对应阶段：`RELEASE`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Release 0.20.0 认证](01-plan-release-certification.md) | [Report](01-report-release-certification.md) | pending |

## 范围

- 从 `develop` 创建 `release/0.20.0`，更新版本号与 CHANGELOG。
- Release gate：wheel 冒烟 + Python 全量 + 前端全量（staging 等价验证）。
- 合并 `release/0.20.0` 到 `main` + `develop`，打 `v0.20.0` tag，整理 CHANGELOG。

## 非范围

- 不包含新功能代码（新需求属下一轮迭代 0076）。
- 不修改已冻结的 ADR/AC 文档。
