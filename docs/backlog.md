# Backlog

工程需求池。DESIGN 阶段的迭代候选只能从这里拉取；选定后状态改为 `planned` 并记录关联迭代。

状态值：`candidate`（待评估）→ `planned`（已排入迭代）→ `done`（已闭环）/ `dropped`（放弃，需注明原因）

| 编号 | 标题 | 描述 | 来源 | 状态 | 关联迭代 |
|------|------|------|------|------|---------|
| BL-001 | 失败分类驱动的重试/续接策略 | 将 agent 调用失败分类（auth/quota、poisoned、transient、task），按类别决定重试、会话续接（continue）或直接失败，替代统一退避重试 | loopany-platform 调研 2026-07-25 | done | 0.21.0 |
| BL-002 | 失败熔断 + 告警节流 | 连续失败达到阈值自动暂停；失败提示只在状态转变和周期性提醒时出现，防告警疲劳 | loopany-platform 调研 2026-07-25 | done | 0.21.0 |
| BL-003 | reconcile 失联宽限期 | 失联 ≠ 失败：run 失联后进入宽限期，宽限期内恢复可调和为成功，避免笔记本睡眠等场景误判 | loopany-platform 调研 2026-07-25 | done | 0.21.0 |
| BL-004 | 调度语义 deferred/supersede/misfire | 队列中等待的任务被取代标记 skipped、条件不满足挂起 deferred、错过触发补发，均不计为失败 | loopany-platform 调研 2026-07-25 | done | 0.21.0 |
| BL-005 | evolve run 自我进化 | 每 N 次 run 触发一次用 run 历史重写 loop 本身的 run（收紧 brief、折叠机械步骤）。业务层 vs 产品层未定 | loopany-platform 调研 2026-07-25 | candidate | — |
| BL-006 | loop 嵌套编排 | workflow 嵌套/组合的下一个大特性，方向未想好 | loopany-platform 调研 2026-07-25 | candidate | — |
| BL-007 | web profile manifest 漂移修复 | 以 test 容器补齐 web profile AC manifest | 0.20.0 发布评估 | candidate | — |
| BL-008 | loop args schema 服务端校验 | Web/API 侧对 loop args 做 schema 校验 | 0.20.0 发布评估 | candidate | — |
| BL-009 | 非 macOS 目录选择器 | Web UI 目录选择器在非 macOS 平台的适配 | 0.20.0 发布评估 | candidate | — |
| BL-010 | AC-010-N-2/E-2 契约漂移裁决 | AC 文本期望 loop.md 缺失/坏 YAML 时回退 workflow.py meta，但 ADR-0031 后实现为强制 loop.md 缺失即跳过；需 DESIGN 裁决对齐文档或实现 | 0081 scheduling profile 落地时发现 | done | 0.21.0 |
| BL-011 | npm audit 既有失败修复 | brace-expansion 经 @vitest/coverage-v8 链 5 high，中断 mr-gate 链 | 0081 mr-gate 验证时发现 | candidate | — |
