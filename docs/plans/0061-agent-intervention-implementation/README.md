# 0061 Agent structured intervention 实现

对应阶段：`DEVELOP`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Agent structured intervention 实现](01-plan-agent-intervention-implementation.md) | [Report](01-report-agent-intervention-implementation.md) | done |

## 背景

0060 已把 Agent structured intervention vNext 固化为 AC/interface/contract/manifest。当前产品仍是旧 schema/单 request/单 respond 形态，需要进入 DEVELOP 替换 planned 节点。

## 范围

- Agent `__loopflow.requests[]` 解析和持久化。
- Intervention vNext read model：`source/options/allow_custom/response:string`。
- options/custom 校验与 batch respond all-or-nothing。
- CLI/Web `intervene()` 注入一致。
- WebUI 多问题表单与一次提交。

## 非范围

- 不实现完整 JSON Schema renderer。
- 不改变 recover/stop 基础状态机。
