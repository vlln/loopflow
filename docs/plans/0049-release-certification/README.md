# 0049 RELEASE 发布认证

对应阶段：`RELEASE`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [发布认证](01-plan-release-certification.md) | [Report](01-report-release-certification.md) | done |

## 范围

- 确认发布版本号和版本一致性
- 整理 CHANGELOG
- 创建 `release/*` 分支
- 执行 release/staging 冒烟和 wheel 安装验证
- 合并 release 到 `main` 与 `develop`
- 创建版本 tag

## 非范围

- 不新增功能
- 不修复非阻塞缺陷；发现缺陷时按 devloop 退回相应阶段
- 不跳过 SYSTEM_TEST 已建立的门禁证据
