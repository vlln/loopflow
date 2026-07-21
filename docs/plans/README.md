## 执行容器列表

| 编号 | 标题 | 状态 | 创建时间 |
|------|------|------|----------|
| [0001](0001-template/) | 模板（参考用） | template | — |
| [0033](0033-webui-design/) | WebUI 契约与架构设计 | done | 2026-07-18 |
| [0035](0035-webui-test-infra/) | WebUI 测试与交付底座 | done | 2026-07-19 |
| [0036](0036-web-application/) | Web Application 服务 | done | 2026-07-19 |
| [0037](0037-develop-manifest-gate/) | DEVELOP manifest 门禁修复 | done | 2026-07-19 |
| [0038](0038-web-api/) | Web API 服务 | done | 2026-07-19 |
| [0039](0039-web-frontend/) | Web Frontend 工作台 | done | 2026-07-19 |
| [0040](0040-webui-system-test/) | WebUI 系统测试 | done | 2026-07-19 |

## 状态说明

| 状态 | 含义 |
|------|------|
| pending | 未执行 |
| done | 已执行（无论成功/失败） |


## 规则

- 执行容器由各阶段根据 Spec 模块划分自行创建
- Agent 权限边界见 [AGENTS.md](../../AGENTS.md)
- 状态在执行容器的 README.md 和本 README 中维护，执行容器原地保留
