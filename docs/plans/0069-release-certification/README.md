# 0069 RELEASE 认证

对应阶段：`RELEASE`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [0.19.1 Release 认证](01-plan-release-certification.md) | [Report](01-report-release-certification.md) | pending |

## 范围

- 确认 `0.19.1` patch 版本策略。
- 更新版本文件与 CHANGELOG。
- 在 release 分支运行 release gate。
- 构建并安装 wheel，确认 Web static assets 可用。
- 本地 Gitflow 合并到 `main` 与 `develop`，创建 tag。

## 非范围

- 不推送远端分支或 tag。
- 不执行外部生产发布流程。
