# 0035 WebUI 测试基础设施

对应分支：`test/0035-webui-test-infra`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [WebUI 测试与交付底座](01-plan-webui-test-infra.md) | [基建报告](01-report-webui-test-infra.md) | pending |

## 范围

- Python/HTTP fixture 与契约 helper
- React/Vite/Vitest/Playwright 测试工作区
- AC 系统测试 manifest 与静态检查器
- MR 门禁、提测门禁、覆盖率与 CI
- Vite 静态资产进入 wheel 的隔离冒烟

本容器不实现 Runs、Loops、Queue、Backends、SSE 或 `loop web` 产品行为。
