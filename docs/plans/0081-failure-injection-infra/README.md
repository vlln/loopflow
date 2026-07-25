# 0081 失败注入测试基础设施

对应阶段：`TEST_INFRA`（0.21.0 迭代，服务 ADR-0044~0047 / AC-026~029）。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [失败注入测试基建](01-plan-failure-injection-infra.md) | [Report](01-report-failure-injection-infra.md) | done |

## 范围

- SessionBackendFake 脚本化 per-attempt 失败注入（exit_code/stderr/error_category/behavior），向后兼容
- 结构化错误通道替身：`agent_done` payload 上报 error_category，支持结构化-vs-stderr 冲突模拟
- stale/grace 测试工厂：run.json fixture 支持 stale_since 相对偏移（秒）
- loop_state（consecutive_failures/paused）与队列条目（status/status_reason/superseded_by）fixtures
- 基建自证：tests/infrastructure/ 新增自证测试
- 依据：ADR-0048

## 非范围

- AC-026~029 的业务测试用例（DEVELOP 阶段职责）
- 生产代码（src/）任何改动
- `manager._run_mock` 扩展（ADR-0048 Alternatives 已否决）
