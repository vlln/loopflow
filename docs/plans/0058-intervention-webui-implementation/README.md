# 0058 Intervention WebUI 实现对齐

对应阶段：`DEVELOP`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Intervention WebUI 实现对齐](01-plan-intervention-webui-implementation.md) | [Report](01-report-intervention-webui-implementation.md) | done |

## 背景

0056 冻结了 WebUI 交互语义，0057 固化了 respond command 错误边界。当前 WebUI 已有最小 schema 控件，但还缺 answered/history 展示、panel-level submit error，以及 `cancelled + pending request` 下 respond 优先于 retry 的视觉层级。

## 范围

- 调整 run toolbar 中 recover/respond 的视觉优先级。
- Intervention panel 支持 pending、answered/history、submit error。
- 多 request 首版以最早 pending 为主，其余只读折叠。
- 回答成功后刷新 Run/read model。

## 非范围

- 不修改后端 command 语义。
- 不引入新的 Intervention lifecycle state。
- 不实现完整 JSON Schema form renderer。
