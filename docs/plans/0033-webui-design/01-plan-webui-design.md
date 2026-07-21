---
title: WebUI 契约与架构设计 Plan
description: 冻结 loopflow 本地 WebUI 的信息架构、验收标准、事件与生命周期契约、技术栈和 Web API。
type: plan
status: done
created: 2026-07-18T20:00:00Z
---

# 目标

在不编写产品业务代码的前提下，完成 WebUI 增量迭代的 DESIGN 证明链，使后续 TEST_INFRA 可以依据冻结契约搭建测试底座。

# Constraints

1. Vision 保持 active，不改变 loopflow 以 Python workflow.py 表达循环的核心定位。
2. Runs 采用常驻主从工作台，不设置独立列表页作为详情入口。
3. Phase title 用于聚合图，phase_id 区分循环中的 occurrence；不得按日志邻近关系虚构 legacy 归属。
4. `<seq>.jsonl` 保持扁平 resume 缓存，`events.jsonl` v2 使用 Web 事件信封。
5. Web 默认只绑定 127.0.0.1；远程绑定需要 host 与 allow-remote 双确认。
6. Loop 文件预览不得越过 Loop 根目录；浏览器不得直接访问本地文件系统。
7. 视觉参数以 `references/DESIGN.md` 为唯一事实源；概念原型只参考结构和风格。
8. DESIGN 阶段禁止实现业务功能；技术代码只能存在于不合并的 spike 分支。

# Steps

1. 推进 RELEASE -> DESIGN，增量更新并审查 Spec v12。
2. 编写并审查 AC-0010，覆盖 Runs、Phase、SSE、Loops、Backends 和布局 N/B/E/F 场景。
3. 编写 ADR 0033/0034，验证标准库 HTTP/SSE、React/Vite/React Flow 和 wheel 静态资产打包。
4. 编写并审查 Web API v1 接口定义。
5. 回填验证证据、冻结文档并核验 DESIGN 门禁。

# Checkpoint

| 检查点 | 通过条件 | 证据 |
|--------|----------|------|
| Spec | status=active、v12、内容独立审查 PASS | commit `dd0c5d8` |
| AC | AC-014..019 每组 N/B/E/F，独立审查 PASS | commit `70cf38d` + `cfccec0` |
| ADR | 0033/0034 accepted，0033 验证全部可行 | commits `a743268`; spike `ba32790`, `3a8b727` |
| Interface | status=active，所有接口有输入/输出/错误，独立审查 PASS | commit `cfccec0` |
| Container | 本执行容器存在于对应归档分支 | `docs/0033-webui-design` 包含本 Plan/Report |
| Scope | develop 无 WebUI 产品代码；spike 未合并 | `git branch --contains 3a8b727` 仅 spike 分支 |

# Exit

全部 Checkpoint 通过后，将 `docs/README.md` 当前阶段推进为 `TEST_INFRA`。TEST_INFRA 必须自行创建对应测试基建执行容器，本 Plan 不替下游定义实现步骤。
