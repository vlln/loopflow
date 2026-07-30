---
title: 0.27.0 增量契约测试基建
description: 为 BL-051/046/052/054 补充 AC manifest、Interface schema fixture 和增量门禁自证
type: plan
status: done
created: 2026-07-29T11:24:49Z
---

# Plan: 0.27.0 增量契约测试基建

## 目标

复用既有 pytest、recovery support、Web contract helper、mock ACP 和 AC checker，仅补齐冻结契约所需的机器可执行测试基建，使 DEVELOP 可直接回填真实测试节点。

## Constraints

- 不编写 BL-046/051/052/054 业务实现或具体 AC 测试用例；manifest 新场景使用 `planned::` 节点。
- 不修改 active Spec/AC/Interface 或 accepted 业务 ADR。
- 不新增测试框架或项目依赖；复用 ADR-0035、0037、0050。
- AC-023 的 `agent_intervention_not_supported` 是异步 Run failure，不映射成 HTTP status。
- batch response schema 必须同时允许 workflow 的任意 JSON 与 Agent 的非空 string；按 source 的业务校验留给 DEVELOP。
- 只对新增 profile、schema 和 manifest 规则执行增量正反向自证，不重复全量一次性基建自证。

## 步骤

1. 扩展 recovery manifest 的 target/expectation 映射，生成 AC-023 新场景 planned 节点。
2. 新建 iteration027 manifest profile，覆盖 AC-033~035 全部 N/B/E/F 场景并冻结 endpoint/status/error/DOM/process expectation。
3. 更新 recovery/Web contract schema，表达统一 InterventionSummary、request group/index、any batch response、FilePreview、DeclaredArg 和 append_prompt create body。
4. 添加基础设施正反例，证明 checker 拒绝缺场景、错误 HTTP 映射和 planned strict mode，schema 拒绝漂移结构。
5. 生成 JSON manifests，运行新增基础设施测试、全部 manifest allow-planned 与既有相关 infra 回归。
6. 记录增量检查和自证 Report；完成后合并到 develop。

## Checkpoint

- [x] 既有测试基建 ADR 覆盖性已审计，无需新增 ADR
- [x] Recovery manifest 覆盖 AC-023 新增场景
- [x] iteration027 manifest 覆盖 AC-033~035 全部场景
- [x] Interface v18 schema fixture 正反向自证通过
- [x] 新增规则的 allow-planned 门禁通过、strict 门禁正确拒绝
- [x] Report 记录结论、依据和证据路径
