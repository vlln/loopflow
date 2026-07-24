# 0080 Hotfix 0.20.1

对应阶段：`RELEASE`（hotfix 快速通道）。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Hotfix 0.20.1](01-plan-hotfix-0.20.1.md) | [Report](01-report-hotfix-0.20.1.md) | done |

## 范围

- 修复 v0.20.0 的三个产品级缺陷（cherry-pick 自 develop，已经 CI 全绿验证）：
  1. recover 时 `execution_options` 中的 mock 未生效（无 backend 机器 sys.exit）
  2. 启动信号窗口 2s 在负载机器误报 `run_process_start_failed`
  3. Python 3.14 forkserver 子进程环境陈旧 → 默认 spawn
- 版本号 0.20.1 + CHANGELOG + tag

## 非范围

- 不引入新功能
- 不做 ADR/AC 变更（无设计变更）
