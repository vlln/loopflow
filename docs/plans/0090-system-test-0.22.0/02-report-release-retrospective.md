---
title: 0.22.0 迭代复盘
description: 0.22.0 发布认证与迭代复盘：BL-014 采用官方 Python ACP SDK
type: report
status: complete
created: 2026-07-25T05:45:00Z
---

# 0.22.0 迭代复盘

发布认证：v0.22.0 tag 在 main（release/0.22.0 → main + develop 已合并，分支已删）。系统测试 527 passed / 1 skipped，4 AC profile strict 全绿（80/69/32/21），浏览器 13 passed，wheel 冒烟 ok。

## 交付

BL-014 采用官方 Python ACP SDK 替换手搓 ACP 管道。容器 0088（mock ACP server 测试基建 + ADR-0050）→ 0089（ACP SDK 真实实现 + AC-030）→ 0090（系统测试）。新增 acp_sdk.py + acp_sdk_backend.py + agent-client-protocol 依赖；CLI 保留为主传输，ACP 成为可选可用路径。

## 工期

DESIGN → RELEASE 单日完成（2026-07-25），含 spike 验证（spike/0049 分支保留不合并）。无工期偏差。

## 关键技术决策（spike 印证）

- sync/async 桥接：专属守护线程 + 持久事件循环（asyncio.run per-op 不可行——会杀 SDK 的 receive-loop）。已写进 ADR-0049 §3。
- permission auto-approve-all 消除 ADR-0018 授权死锁；mock server 验证机制就绪。
- pi-acp loadSession=true、session/load 保留上下文 → continue 在 ACP 可行（BR-057 能力门控）。

## 问题与改进

| 问题 | 根因 | 改进 |
|------|------|------|
| ADR-0049 §8 的可选 extra `[acp]` 划分未做，依赖暂放主依赖区 | 0088/0089 实现阶段为简化直接主依赖 | BL-015：RELEASE 后做 extra 划分，使默认安装不含 pydantic |
| 版本号仍双写（pyproject + __init__.py），release 时手动同步两处 | BL-013 未做 | 维持 BL-013 candidate，下轮处理 |
| grok ACP 的 `_meta` system prompt 在 SDK 路径不生效 | SDK session/new 不接受 _meta，改走 prompt 文本拼接 | 记入 backlog（BL-016），非阻塞 |
| AC-030-B-2（未装 extra 报错）用常量 mock 验证，真实触发需 extra 划分 | 依赖未做 extra 划分 | 随 BL-015 一并验证 |

## 改进点录入 backlog

- BL-015 agent-client-protocol 划为可选 extra [acp]（candidate）
- BL-016 grok ACP `_meta` system prompt 在 SDK 路径的等价处理（candidate）
