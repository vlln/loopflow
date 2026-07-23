# 0055 Intervention 前后端契约对齐

对应阶段：`DESIGN`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Intervention 前后端契约对齐](01-plan-intervention-frontend-contract.md) | [Report](01-report-intervention-frontend-contract.md) | done |

## 背景

0054 修正了 InterventionSummary 字段漂移，但前端回答问题的交互仍只完整覆盖 boolean，其他 schema 退化为 JSON textarea。需要把用户回答问题这条介入链路按活跃接口契约重新对齐。

## 范围

- Web contract 增加 InterventionSummary schema。
- Web API 集成测试校验 intervention list 的完整响应形状。
- WebUI 根据 intervention schema 渲染 boolean/string/number/JSON 输入。
- WebUI 测试覆盖 waiting_input 与 cancelled pending request 的回答路径。

## 非范围

- 不改变 Run status 集合。
- 不改变 recover/respond 状态转换。
- 不引入完整 JSON Schema 表单生成器。
