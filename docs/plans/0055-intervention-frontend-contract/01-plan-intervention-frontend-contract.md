---
title: Intervention Frontend Contract Plan
description: 对齐用户回答问题介入链路的后端 contract、Web API 测试和 WebUI 控件
type: plan
status: done
created: 2026-07-23T14:30:00Z
---

# Goal

让用户回答问题的 Intervention 链路在后端契约、API 测试、前端类型和 UI 行为上保持一致。

# Acceptance

1. Web support contract 覆盖 InterventionSummary，字段与 Interface 0001 一致。
2. Web API 集成测试校验 `GET /runs/{run_id}/interventions` 的完整字段。
3. WebUI 按 schema 类型提交正确 JSON 值：
   - boolean: true/false button
   - string: text input
   - number: number input
   - object/array/null: JSON textarea
4. WebUI 仍支持 cancelled + pending request 的 `respond`。
5. 错误返回时保留工作台并显示 API error toast。

# Steps

1. 增加 Web contract InterventionSummary schema 和 example。
2. 强化 Web API integration test 的 contract validation。
3. 更新 WebUI InterventionPanel schema 渲染和提交逻辑。
4. 增加 Web unit tests 覆盖 string/number/JSON/null/error。
5. 运行 Python/Web 相关测试和 manifest。
6. 写 Report、标记 done 并提交。

# Exit

验收通过后保持 DESIGN 阶段，等待下一轮功能设计。
