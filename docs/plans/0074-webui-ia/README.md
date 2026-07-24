# 0074 WebUI 信息架构收敛

对应阶段：`DEVELOP`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [WebUI 信息架构收敛](01-plan-webui-ia.md) | [Report](01-report-webui-ia.md) | done |

## 范围

- 背景：v0.20.0 发布前人工验收发现 Runs 视图存在呈现层缺陷（信息重复表达、面板结构不统一、文件变化展示粗糙、布局不贴合真实使用场景），作为 0070/0071/0072 的呈现层修正随 0.20.0 发布。
- Runs 视图信息架构收敛：去重、三栏任务分工。
- 面板头部抽象（PanelHeader / SectionHeader）与字号标尺统一。
- 文件变化目录树 + per-phase 标记随选中 phase 切换。
- Intervention 横幅位置、折叠按钮显隐修正。

## 非范围

- 不改后端 API 与文件观察语义（per-run working directory、观察基线语义属后续迭代容器）。
- 不改 Python 侧代码。
