# 0077 SYSTEM_TEST 认证（含 0076）

对应阶段：`SYSTEM_TEST`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [系统测试认证](01-plan-system-test-certification.md) | [Report](01-report-system-test-certification.md) | pending |

## 范围

- 在 `develop` 上对 0076（ADR-0042/0043、BR-046）及 0070-0074 全部待发布内容进行系统级验证。
- Python 全量测试 + 覆盖率、前端全量、AC manifest strict（全部 profile）、Playwright e2e、wheel 冒烟。
- 对预先存在的 web profile（AC-014..019）manifest 漂移进行失败分类。
- 给出是否可重新进入 RELEASE（0.20.0）的结论。

## 非范围

- 不新增 feature/fix 代码（缺陷修复另立容器）。
- 不创建 release 分支或 tag。
