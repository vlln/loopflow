# 0071 Declared Phases 预显示

对应阶段：`DEVELOP`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Declared phases 预显示实现](01-plan-declared-phases.md) | [Report](01-report-declared-phases.md) | done |

## 背景

ADR-0040 已 accepted。WebUI 和终端在 Run 创建时从 `meta.phases` 预显示占位节点，运行时按 title 匹配合并 runtime events。

## 范围

- Loop discovery 提取 `meta.phases` 声明
- 终端 graph renderer 在 Run 启动时预显示占位节点
- WebUI phase graph 在 Run 创建时预显示 pending 占位节点
- 运行时 phase 事件按 title 匹配替换占位节点
- undeclared phase 出现时标记 badge
- 无声明时退化为现有涌现行为

## 非范围

- 不实现文件变化观察（属于 0072）
- 不改变 ADR-0009 的运行时涌现拓扑语义
- 不实现 phase 的 detail 字段渲染（首版只显示 title）

## 依赖

- 无前置依赖，可与 0070 并行
