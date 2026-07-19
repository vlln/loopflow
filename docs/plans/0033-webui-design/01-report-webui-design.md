---
title: WebUI 契约与架构设计 Report
description: 记录 WebUI DESIGN 迭代的冻结文档、独立审查、spike 结果和下游约束。
type: report
status: complete
created: 2026-07-18T23:00:00Z
---

# 结果

WebUI 增量 DESIGN 已完成，契约链为：

`Spec v12 -> AC-0010 + ADR 0033/0034 -> spike validation -> Interface 0001`

## 冻结文档

| 文档 | 状态 | 结果 |
|------|------|------|
| Spec 0001 v12 | active | Runs/Loops/Backends 主从工作区、phase_id、事件信封、stale reconcile 已冻结 |
| AC 0010 | active | AC-014..019 均覆盖 N/B/E/F，预期结果已收敛为单一可测试契约 |
| ADR 0033 | accepted | 标准库 HTTP + REST/SSE + React/TypeScript/Vite + React Flow 可行 |
| ADR 0034 | accepted | v2 events、扁平 cache、legacy、原子写和 Run 生命周期已冻结 |
| Interface 0001 | active | Runs、Events、Loops、Queue、Backends 的输入/输出/错误已冻结 |

## Branches

- 执行容器：`docs/0033-webui-design`，归档本 Plan/Report 与冻结契约证据。
- 技术验证：`spike/0033-webui-architecture`，只含最小验证代码，保留不合并。

## Spike

分支：`spike/0033-webui-architecture`，提交 `ba32790`、`3a8b727`，未合并。

| 项目 | 结果 |
|------|------|
| 标准库 SSE | 重放、增量、游标重连、8 客户端断连回收通过 |
| 慢客户端 | 1KB 接收缓冲不读时，约 16MB append < 2s，正常客户端收到最终事件 |
| 路径与绑定 | loopback 默认、remote 双确认、路径穿越和 symlink escape 拒绝通过 |
| React Flow | 分支、回边、current、100 occurrence fixture、选择回调和 production build 通过 |
| 前端依赖 | Vite 7.3.6 / Vitest 3.2.7，npm audit 0 vulnerabilities |
| Wheel | Vite 资产同步入 Python 包目录后可从 isolated Python 通过 importlib.resources 读取 |

缩放、fit view、视觉布局和像素回归未由 jsdom 证明，明确进入 TEST_INFRA 的真实浏览器门禁。

## 审查修正

独立审查共推动以下关键修正：

- 引入 phase_id，区分循环中同名 Phase occurrence。
- legacy 并行歧义统一标记 unattributed，不按文件顺序猜测。
- Phase 首版只承诺 Calls/Events，Run state 保持 Run 级。
- stale Run 增加显式 reconcile 状态闭环。
- SSE、错误信封、脱敏、unreadable DTO 和 API 字段全部收敛为唯一契约。
- 技术验证结论严格限制在实际测试证据范围内。

## 下游约束

TEST_INFRA 需要优先建立契约测试、事件故障注入、进程身份 mock、SSE 慢客户端测试、前端组件测试以及 1440/1024/390 三视口的真实浏览器截图和无重叠检查。未完成这些基建门禁前不得进入 DEVELOP。
