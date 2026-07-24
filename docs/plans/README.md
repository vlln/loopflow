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
| [0042](0042-recovery-controls-infra/) | 恢复控制测试基础设施 | done | 2026-07-22 |
| [0043](0043-recovery-engine/) | 确定性恢复引擎 | done | 2026-07-22 |
| [0044](0044-reliable-stop/) | 可靠停止 | done | 2026-07-22 |
| [0045](0045-intervention-control/) | 阻塞人工介入 | done | 2026-07-22 |
| [0046](0046-grok-backend/) | Grok 后端接入 | done | 2026-07-22 |
| [0047](0047-grok-acp/) | Grok ACP 接入 | done | 2026-07-22 |
| [0048](0048-system-test-certification/) | SYSTEM_TEST 发布前认证 | done | 2026-07-23 |
| [0049](0049-release-certification/) | RELEASE 发布认证 | done | 2026-07-23 |
| [0050](0050-cancel-recovery-semantics/) | 取消恢复语义设计修订 | done | 2026-07-23 |
| [0051](0051-cancel-recovery-test-infra/) | 取消恢复测试契约同步 | done | 2026-07-23 |
| [0052](0052-cancel-recovery-implementation/) | 取消恢复语义实现 | done | 2026-07-23 |
| [0053](0053-system-test-certification/) | 取消恢复后 SYSTEM_TEST 认证 | done | 2026-07-23 |
| [0054](0054-status-contract-alignment/) | 状态契约对齐 | done | 2026-07-23 |
| [0055](0055-intervention-frontend-contract/) | Intervention 前后端契约对齐 | done | 2026-07-23 |
| [0056](0056-intervention-webui-design/) | Intervention WebUI 设计 | done | 2026-07-23 |
| [0057](0057-intervention-respond-test-infra/) | Intervention respond 错误边界测试契约 | done | 2026-07-23 |
| [0058](0058-intervention-webui-implementation/) | Intervention WebUI 实现对齐 | done | 2026-07-23 |
| [0059](0059-agent-intervention-design/) | Agent structured intervention 设计修订 | done | 2026-07-23 |
| [0060](0060-agent-intervention-test-infra/) | Agent structured intervention 测试契约 | done | 2026-07-23 |
| [0061](0061-agent-intervention-implementation/) | Agent structured intervention 实现 | done | 2026-07-23 |
| [0062](0062-system-test-certification/) | SYSTEM_TEST 发布前认证 | done | 2026-07-23 |
| [0063](0063-system-test-fix/) | SYSTEM_TEST 局部修复 | done | 2026-07-23 |
| [0064](0064-release-certification/) | RELEASE 认证 | done | 2026-07-23 |
| [0065](0065-intervention-choice-compatibility/) | Intervention Choice 兼容修复 | done | 2026-07-23 |
| [0066](0066-webui-primitives-refactor/) | WebUI 基础组件整理 | done | 2026-07-24 |
| [0067](0067-hide-gork-backend-alias/) | 隐藏 gork backend 别名 | done | 2026-07-24 |
| [0068](0068-system-test-certification/) | SYSTEM_TEST 认证 | done | 2026-07-24 |
| [0069](0069-release-certification/) | RELEASE 认证 | done | 2026-07-24 |
| [0070](0070-sse-multi-topic-transport/) | SSE 多 topic 传输层 | done | 2026-07-23 |
| [0071](0071-declared-phases-predisplay/) | Declared phases 预显示 | done | 2026-07-23 |
| [0072](0072-file-change-observation/) | 工作目录文件变化观察 | done | 2026-07-23 |
| [0073](0073-system-test-certification/) | SYSTEM_TEST 认证 | done | 2026-07-24 |
| [0074](0074-webui-ia/) | WebUI 信息架构收敛 | done | 2026-07-24 |
| [0075](0075-release-certification/) | RELEASE 认证（0.20.0） | pending | 2026-07-24 |
| [0076](0076-run-working-directory/) | Run 显式工作目录与观察语义 | done | 2026-07-24 |
| [0077](0077-system-test-recertification/) | SYSTEM_TEST 认证（含 0076） | done | 2026-07-24 |
| [0078](0078-new-run-dialog-ux/) | New Run 对话框 UX（目录选择器 + Arguments 编辑器） | done | 2026-07-24 |

## 状态说明

| 状态 | 含义 |
|------|------|
| pending | 未执行 |
| done | 已执行（无论成功/失败） |


## 规则

- 执行容器由各阶段根据 Spec 模块划分自行创建
- Agent 权限边界见 [AGENTS.md](../../AGENTS.md)
- 状态在执行容器的 README.md 和本 README 中维护，执行容器原地保留
