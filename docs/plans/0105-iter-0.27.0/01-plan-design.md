---
title: 0.27.0 增量设计
description: 为 BL-051/046/052/054 修订 Spec、AC、接口定义并形成 Agent waiting_input 协议 ADR
type: plan
status: done
created: 2026-07-29T11:24:49Z
---

# Plan: 0.27.0 增量设计

## 目标

完成本轮四项需求的契约设计、独立审查和阶段末统一冻结准备，不编写业务代码。

## Constraints

- 遵循 Vision -> Spec -> AC/ADR -> 验证 -> Interface 的因果顺序；仅审查本轮增量。
- 已 accepted 的 ADR 不原地改写；BL-046 用新 ADR 扩展 ADR-0036/0056。
- BL-051 的既有实现和 Report 只能作为现状证据，不能替代 active AC；先消除当前二进制预览契约冲突。
- Agent waiting_input 不从自然语言推断，只接受显式框架控制对象。
- BL-046 不允许在缺少 durable session 时静默重跑 Agent；自动重跑可能重复外部副作用，且无法保证与原会话等价。
- 业务输出 schema 与框架控制 schema 必须可组合，不能要求 Agent 伪造业务字段才能请求输入。
- 权威文档保持 proposed，阶段末经人类统一确认后才 promote。

## 步骤

1. 将 Spec 升至 v18 proposed，补充四项用户故事、业务规则、数据和 UI 约束。
2. 为 BL-046 新建 ADR，定义控制提示、联合 schema、回答信封和 capability 边界；复用 `uv.lock` 中现有锁定依赖完成可行性验证，不新增项目依赖。
3. 修订 AC-023，并为 BL-051/052/054 补齐正常、边界、异常、失败场景。
4. 修订 Web API 接口中的二进制 raw 端点、预览响应和 declared args 契约。
5. 由不携带编写上下文的独立审查者按 devloop 审查表检查每层文档，修复问题。
6. 形成并提交阶段末确认简报；统一 promote 和进入 TEST_INFRA 置于本容器完成后的不可委托人类门禁。

## BL-046 设计检查点

- 支持 intervention 的 Agent 在初始 prompt 中能读到明确、最小、可复制的 `__loopflow` 协议。
- 有业务 output schema 时，有效 schema 表达“业务结果或 waiting_input 控制对象”，两者互斥且控制对象不泄漏给 workflow。
- goal 模式下，正常结果仍满足 `__goal`；waiting_input 作为独立控制分支优先处理。
- 只有已获得 durable session id 且 backend 声明 resume 能力时才落盘 Agent request。
- 能力不足时不创建 pending request，Run 以明确错误失败，并提示改用 workflow `intervene()` 或支持续接的 backend。
- 回答通过稳定的框架信封发送到原 session；多问题回答保持 key/response 对应关系。

## Checkpoint

- [x] Spec v18 proposed 且增量审查通过
- [x] BL-046 ADR proposed，验证段非空且审查通过
- [x] 增量 AC 四场景齐全并审查通过
- [x] Web API 接口入参、出参、错误码完整并审查通过
- [x] 阶段末确认简报已提交给人类，未提前 promote
