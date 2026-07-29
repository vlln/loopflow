---
title: 0.27.0 增量契约测试基建 Report
description: 记录 BL-051/046/052/054 的 manifest、Interface v18 schema fixture 与增量门禁自证
type: report
status: complete
created: 2026-07-29T13:20:37Z
---

# Summary

0106 已完成 TEST_INFRA 增量搭建。既有 ADR-0035、ADR-0037、ADR-0050 已覆盖 pytest、Web contract、recovery manifest 与 mock ACP 能力，无需新增测试基建 ADR。新增基建没有修改 `src/` 或 Web 业务实现；AC-023 新增 14 个场景与 AC-033~035 共 29 个场景均保持 `planned::`，留待 DEVELOP 回填真实测试节点。

# Changes

| 层 | 内容 |
|----|------|
| Recovery manifest | 补齐 AC-023-N-6~F-5 的 target/expectation；异步 `agent_intervention_not_supported` 不映射为 HTTP 错误 |
| 0.27.0 profile | 新增 `iteration027` profile 与 29 场景 JSON manifest，锁定文件预览、append_prompt、declared args 的 HTTP/CLI/DOM/unit 目标 |
| Recovery contract | 统一 Intervention read model，加入 schema、group/index、call/session、timeout 与回答来源；batch response 接受任意 JSON |
| Web contract | 新增 `intervention_v18`、FilePreview text/raw union、DeclaredArg、Loop declared_args 和 Run create body；append_prompt 使用 UTF-8 65536-byte 语义校验 |
| 门禁 | `check-ac-manifest.py`、`mr-gate.sh`、GitHub Python job 接入 iteration027；CI 同时检查 recovery 增量 |
| 自证 | 新增正反例，验证缺失/重复 AC、错误 HTTP code、strict planned 拦截、schema shape drift 与 UTF-8 边界 |

# Incremental Gate

| 检查项 | 结论 | 依据 / 证据路径 |
|--------|------|-----------------|
| 既有 ADR 覆盖本轮需求 | PASS | [ADR-0035](../../adr/0035-webui-test-infrastructure.md)、[ADR-0037](../../adr/0037-recovery-test-infrastructure.md)、[ADR-0050](../../adr/0050-mock-acp-test-infra.md) 已覆盖所需栈；无新框架、依赖或外部服务 |
| 新增 manifest 完整性 | PASS | `tests/infrastructure/test_recovery_manifest.py`、`tests/infrastructure/test_iteration_027_manifest.py` 核对 AC source、提交 JSON、target 与 expectation |
| Interface fixture 正反向 | PASS | `tests/infrastructure/test_recovery_support.py`、`tests/infrastructure/test_web_test_support.py` 覆盖合法与漂移 shape |
| allow-planned 门禁 | PASS | web 86、recovery 98、scheduling 32、agent 26、singleagent 9、iteration027 29 scenarios 全部通过 |
| strict 正确拦截 | PASS | recovery 仅拒绝 14 个新增 planned nodes；iteration027 仅拒绝 29 个 planned nodes；其他错误均为 0 |
| 既有 API 契约兼容 | PASS | `uv run pytest tests/integration/test_web_api.py -k intervention -q`：2 passed、42 deselected；v17 fixture 保留至 DEVELOP 迁移真实 API 测试 |
| Python CI 可运行 | PASS | `uv run pytest tests/ -q --junitxml=.artifacts/0106-python-junit.xml`：561 passed、1 skipped；机器证据位于 `.artifacts/0106-python-junit.xml` |
| 范围边界 | PASS | develop squash commit `15e62b0` 未修改产品实现、active 设计文档或具体 AC 业务测试用例 |

# Notes

- Web support 使用版本化的 `intervention_v18` fixture，避免 TEST_INFRA 直接使当前 v17 产品契约测试变红。DEVELOP 实现统一 read model 后，应将真实 API 测试迁到 v18 并删除 legacy fixture。
- JSON Schema 无法表达 UTF-8 编码后的字节数；`validate_contract("run_create", ...)` 在结构校验后执行 65536-byte 语义校验，并以多字节字符正反例自证。
- `responses[].response` 在 batch body fixture 中保持任意 JSON；Agent 非空 string 与 options/allow_custom 属于按 source 的业务校验，由 DEVELOP 测试覆盖。

# Next

进入 DEVELOP 后按 BL-046、BL-051、BL-052、BL-054 分解 feature Plan，以真实测试节点替换本轮 43 个 `planned::` 节点，并让 iteration027/recovery strict profile 通过。
