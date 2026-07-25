---
title: 失败注入测试基础设施 Plan
description: SessionBackendFake 脚本化失败注入 + 结构化 error_category 通道 + stale_since/loop_state/queue fixtures + 基建自证
type: plan
status: done
created: 2026-07-25T04:55:00Z
---

# Goal

为 0.21.0 四特性（ADR-0044 失败分类、ADR-0045 熔断、ADR-0046 stale 宽限、ADR-0047 队列状态，AC-026~029 共 30 场景）搭建失败注入测试基建，使 DEVELOP 阶段能直接表达失败序列、失败分类、stale 时间窗口与熔断/队列状态，无需各自临时拼 fixture。依据 ADR-0048。

# Constraints

- 生产代码（src/）一行不改；发现基建必须依赖的业务改动时记录在本节约给 DEVELOP
- `SessionBackendFake` 完全向后兼容：现有字段默认值行为不变，既有调用方（tests/infrastructure/test_recovery_support.py）零修改通过
- 注入 seam 复用既有通道：fake 实现 `create_session`/`resume_session` 接口，经 `loopflow.runtime._make_backend` patch 注入（与 tests/unit/test_runtime.py 同模式），不新增生产侧接缝
- stale_since 用相对偏移（秒）直接构造持久化时间戳，不要求生产代码时钟注入
- fixtures 复用 conftest 的 `LOOPFLOW_HOME` 临时隔离与 recovery_support 既有原子写模式
- **不编写 AC-026~029 业务测试用例**（DEVELOP 职责）；本容器只交付基建与自证

# Steps

1. `tests/recovery_support/fakes.py`：`AttemptResult` 值对象 + `SessionBackendFake` 增加 `create_script`/`resume_script`（每次调用消费一项，耗尽回退既有字段）；`agent_done_payload()` 按 ADR-0044 产出 exit_code/stderr/error_category payload
2. `tests/recovery_support/failure.py`：测试侧参考实现 `resolve_error_category()`——结构化上报优先、stderr 模式兜底（复用 runner 的 `_TRANSIENT_PATTERNS`），固化 ADR-0044 §1 优先级
3. `tests/recovery_support/fixtures.py`：run.json 工厂（stale_since 相对偏移）、`LoopStateFactory`（consecutive_failures/paused/...）、`QueueEntryFactory`（status/status_reason/superseded_by）
4. `tests/recovery_support/__init__.py` 导出新符号
5. `tests/infrastructure/test_failure_injection_support.py` 自证：脚本序列消费、四类失败上报、结构化-vs-stderr 冲突优先级、stale_since 偏移、loop_state/queue fixture 往返、既有 fake 行为回归
6. 验证：pytest unit+infrastructure 全绿；check-ac-manifest 双 profile（--allow-planned）；mr-gate 核心项；回填 ADR-0048 Verification

# Acceptance

- 自证测试覆盖 ADR-0048 Decision 1-5 全部要点且通过
- `uv run pytest tests/unit/ tests/infrastructure/ -v` 全绿，既有测试零回归
- `python3 scripts/check-ac-manifest.py --allow-planned` 与 `--profile recovery --allow-planned` 通过
- 本容器不涉及 AC-026~029 场景实现（planned:: 占位保持）

# Checkpoint

- fake 脚本化扩展完成后先跑既有 test_recovery_support.py 确认零回归，再写新自证
- 合入前双 profile manifest 检查通过

# Exit

全部 Acceptance 通过，ADR-0048 Verification 回填并转 accepted，写 Report，合回 develop。
