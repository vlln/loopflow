---
title: System Test Recertification Report
description: 0076 合并后 develop 全量系统级验证结果与 0.20.0 重新发布就绪判定
type: report
status: done
created: 2026-07-24T06:10:00Z
---

# Summary

0076（ADR-0042/0043、BR-046）及全部待发布内容（0070-0074）系统级验证通过，无阻塞级缺陷，可重新进入 RELEASE 执行 0.20.0。

# Verification Results

## 1. Python 全量测试 + 覆盖率

| 指标 | 结果 |
|------|------|
| 测试总数 | 401 passed, 1 skipped |
| 覆盖率 | 81.78%（阈值 59%） |

## 2. 前端全量

| 指标 | 结果 |
|------|------|
| vitest | 24 passed（3 test files） |
| typecheck | clean |
| build | 成功，静态资源已同步 |
| Playwright e2e | 10 passed, 2 skipped（chromium-390/1024/1440） |

## 3. AC manifest

| Profile | 结果 |
|---------|------|
| file_changes（AC-024）strict | 0 错误，20 cases，0 planned nodes |
| recovery | ok（55 scenarios） |
| web（AC-014..019） | **失败（预先存在，与 0076 无关）**：AC-016-N-1/N-2 断言漂移；12 个 AC id 缺失（AC-015-B-3,B-4,E-3,F-3,N-6,N-7,N-8；AC-016-B-3,E-3,F-3,N-3,N-4） |

## 4. wheel 冒烟

| 指标 | 结果 |
|------|------|
| scripts/wheel-smoke.sh | wheel 构建 + 安装 + 资产验证通过（develop 当前版本号 0.19.1；0.20.0 版本号将在 release 分支 prepare 时更新并重跑） |

# 失败分类

| 失败 | 分类 | 依据 |
|------|------|------|
| web profile manifest 漂移 | 基建缺陷（非阻塞） | 在 0076 合并前的 dbb6233 上以相同错误复现；源于 0070-0072 迭代（4dd5226 起）AC 文档与 `tests/system/cases.json` 未同步；不影响产品功能正确性（相关功能由 401 pytest + 10 e2e 覆盖），影响的是 AC→系统测试用例的追溯完整性 |

# 阻塞级缺陷判定

**无阻塞级缺陷。** 0076 三个方向的功能链路（REST 传参 → 子进程 chdir → 观察/预览）由 AC-025 全场景自动化覆盖；web profile manifest 漂移判定为非阻塞基建缺口，建议另立 `test/*` 容器补齐 `cases.json` 与断言文本，不阻塞 0.20.0 发布。

# 结论

可重新进入 RELEASE，0075 容器继续执行 0.20.0（内容：0070-0072 + 0074 + 0076）。
