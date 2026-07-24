# 0066 WebUI Primitives Refactor

对应阶段：`DEVELOP`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [WebUI 基础组件与滚动区域整理](01-plan-webui-primitives-refactor.md) | [Report](01-report-webui-primitives-refactor.md) | pending |

## 背景

WebUI 已支持 runs、loops、backends 与 intervention 操作，但基础组件仍主要散落在 `App.tsx` 与页面局部 CSS 中。滚动区域、空状态、状态标签、图标按钮等外观和结构存在重复，后续继续扩展 intervention 表单和运行详情时会放大维护成本。

## 范围

- 提取已有 WebUI 基础组件，不改变 API 与业务行为。
- 统一滚动区域样式，优先覆盖 runs/loops/backends/intervention 等已有滚动容器。
- 保持现有测试选择器、按钮语义和页面信息结构稳定。
