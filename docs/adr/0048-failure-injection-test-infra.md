---
title: ADR 0048 — 失败注入测试基础设施
description: 为 0.21.0 四特性（ADR-0044~0047）搭建测试基建：SessionBackendFake 脚本化 per-attempt 失败注入与结构化 error_category 上报替身、stale_since 相对偏移 run.json 工厂、loop_state 与队列状态 fixtures；自证落在 tests/infrastructure，不写 AC-026~029 业务用例
type: adr
status: proposed
created: 2026-07-25T04:50:00Z
---

# ADR 0048: 失败注入测试基础设施

## Context

0.21.0 DESIGN 冻结了四个特性（ADR-0044 失败分类、ADR-0045 熔断、ADR-0046 stale 宽限、ADR-0047 队列状态，共 30 个 AC 场景），但现有测试基建表达不了它们的失败语义：

- `backends/manager.py` 的 `_run_mock` 只有 bash/auto 两种固定模式，无失败注入能力
- `SessionBackendFake`（ADR-0037 交付）只有 `success`/`exception`/`block` 三种行为与**固定** exit code：无失败类别（auth/quota/transient/task）、无 per-attempt 脚本，表达不了"transient 失败 2 次后成功"这类重试序列
- 无 run.json `stale_since`、loop_state（`consecutive_failures`/`paused`）、队列条目（`status`/`status_reason`/`superseded_by`）的测试工厂——这些字段是 ADR-0045~0047 新声明的持久化契约

没有这层基建，DEVELOP 阶段每个特性都要各自临时拼 fixture，且失败序列的表达方式会发散。

## Decision

### 1. SessionBackendFake 脚本化 per-attempt 结果

扩展 `tests/recovery_support/fakes.py` 的 `SessionBackendFake`：新增 `create_script` / `resume_script`（`AttemptResult` 列表）。每次 `create_session`/`resume_session` 消费一个脚本项（`exit_code`、`stderr`、`error_category`、`behavior`），脚本耗尽后回退到既有固定字段——**现有字段默认值行为完全不变**，向后兼容。

### 2. 结构化错误通道替身

fake 按 ADR-0044 契约提供 `agent_done_payload()`：产出 `exit_code` + `stderr` + `error_category` 的事件 payload 形态。结构化上报（`error_category`）与 stderr 文本可同时设置且**故意冲突**（如 `error_category="auth"` + stderr 命中 transient 模式），供 DEVELOP 验证"结构化优先、stderr 兜底"的分类优先级。`tests/recovery_support` 提供测试侧参考实现 `resolve_error_category()` 固化该优先级规则。

### 3. stale/grace 测试工厂

run.json fixture 生成器支持 `stale_since` 相对偏移（秒），直接构造持久化时间戳——**生产代码不需要时钟注入**：`stale_since` 是落盘字段，测试按偏移量构造即可（宽限期判定是相对当前时间的纯读比较）。

### 4. loop_state 与队列 fixtures

`tests/recovery_support/fixtures.py` 新增写入 helper：loop_state 文件（`consecutive_failures`/`paused`/`paused_reason`/`paused_at`/`last_run_id`）与队列条目（`status`/`status_reason`/`superseded_by`），复用 conftest 的 `LOOPFLOW_HOME` 临时隔离与既有原子写模式。

### 5. 自证在 tests/infrastructure/

基建自证测试覆盖：脚本序列消费、四类失败（auth/quota/transient/task）上报、结构化-vs-stderr 冲突优先级、stale_since 偏移工厂、loop_state/queue fixture 往返、既有 fake 行为回归。**不编写 AC-026~029 的业务测试用例**——那是 DEVELOP 阶段职责。

## Alternatives

| 方案 | 评估 |
|------|------|
| 生产代码注入时钟（Clock 接口穿透 web_storage/runner） | 不采纳。`stale_since` 是持久化字段，测试直接构造偏移时间戳即可覆盖宽限期窗口两侧；为测试给生产链路加时钟接缝是过度设计 |
| 扩展 `manager._run_mock` 支持失败模式 | 不采纳。CLI 级 mock 是端到端冒烟的粗粒度替身，表达不了 per-attempt 序列与结构化上报；fake 走 recovery_support 既有 seam（`create_session`/`resume_session` 接口，经 `_make_backend` patch 注入），粒度正好 |

## Consequences

- 服务 ADR-0044~0047 / BR-049~053；本 ADR 自身不引入 AC，正确性由 tests/infrastructure 自证测试证明
- `SessionBackendFake` 既有调用方（tests/infrastructure/test_recovery_support.py）零修改通过——向后兼容由自证回归项直接证明
- DEVELOP 阶段四特性的业务测试统一从本基建取 fixture，不再各自拼装
- 生产代码（src/）零改动；若 DEVELOP 发现基建缺口，回本容器扩展而非就地发散

## Architecture Boundary

全部落在 `tests/`：`recovery_support/fakes.py`（脚本化 fake 与结构化通道）、`recovery_support/failure.py`（分类优先级参考实现）、`recovery_support/fixtures.py`（run.json/loop_state/queue 工厂）、`tests/infrastructure/`（自证）。src/ 一行不改。

## Verification

待验证：基建搭建完成后以 tests/infrastructure 自证测试通过回填（自证测试名称与结果）。
