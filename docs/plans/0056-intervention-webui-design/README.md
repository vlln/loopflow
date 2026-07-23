# 0056 Intervention WebUI 设计

对应阶段：`DESIGN`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Intervention WebUI 设计](01-plan-intervention-webui-design.md) | [Report](01-report-intervention-webui-design.md) | pending |

## 背景

0054/0055 已经修正了 InterventionSummary 字段和最小 WebUI 控件，但执行顺序越过了 devloop 的 DESIGN → TEST_INFRA → DEVELOP 证据链。当前需要回到 DESIGN，先把用户回答问题的 WebUI 产品语义补完整，再决定是否调整已有实现。

## 范围

- 设计 waiting_input 与 cancelled + pending intervention 的首屏信息架构。
- 设计 respond、recover_retry、recover_continue、rerun 的视觉层级和文案。
- 设计 pending/answered/error intervention 的展示规则。
- 冻结首版支持的 schema UI 范围与非范围。

## 非范围

- 不修改产品代码。
- 不修改测试代码。
- 不推进阶段状态。
