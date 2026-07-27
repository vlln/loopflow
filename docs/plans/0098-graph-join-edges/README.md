# 0098 — agent graph live-run join 边修复（BL-028）

对应阶段：`DEVELOP`（微变更）。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | inline | inline | done |

## 范围
- BL-028：`project_events()` back-to-back join 边从 fork_end 提前到 agent_start
- 完成态输出不变，不完整前缀变正确

## 非范围
- 不改前端渲染逻辑
- 不改事件写入逻辑
