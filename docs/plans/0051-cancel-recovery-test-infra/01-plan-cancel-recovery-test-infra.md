---
title: Cancel Recovery Test Infrastructure Plan
description: 同步取消恢复语义的 recovery manifest、fixture 和 contract 基础设施
type: plan
status: done
created: 2026-07-23T12:45:00Z
---

# Goal

完成 0050 后续的 TEST_INFRA 更新，使测试基础设施准确表达新取消恢复契约，并为 DEVELOP 阶段提供严格的 planned 节点清单。

# Acceptance

1. `tests.recovery_support.manifest.generate_manifest()` 覆盖 AC-020..022 当前全部场景。
2. AC-021/022 新语义场景有冻结 target、expectation 和 planned test node。
3. 旧的 “waiting_input stop closes request” 和 “cancelled recover invalid transition” 测试节点不再被 manifest 视为实现证据。
4. contract/fixture 自证覆盖 cancelled Run 可携带 recover/respond actions，以及 atomic worker continue forbidden 的表达。
5. 运行 recovery infrastructure 相关测试通过，不修改产品代码。

# Steps

1. 修订 recovery manifest target mapping，加入 AC-021-N-3、AC-021-B-3、AC-021-B-4、AC-022-N-5、AC-022-B-3。
2. 移除或降级已失效的旧产品 test_node 映射，使相关场景保持 planned。
3. 更新 `tests/system/recovery_cases.json` planned manifest。
4. 增加/修订基础设施自证测试，验证 schema/fixture 能表达 cancelled recover/respond 与 atomic continue forbidden。
5. 运行专项测试和 `git diff --check`。
6. 写 Report 并标记本容器 done。

# Checkpoints

| 检查点 | 通过条件 | 证据 |
|--------|----------|------|
| Manifest | 37 个 AC-020..022 场景全部覆盖，无缺失/重复 | Report |
| Planned | 新语义未实现节点保持 planned，strict checker 能拦截 | Report |
| Contract | cancelled allowed_actions 与 atomic metadata 表达通过 schema/fixture 自证 | Report |
| Scope | 不修改产品代码 | Report |
| Tests | recovery infrastructure 专项通过 | Report |

# Exit

Report complete，Plan/container 标记 done，并提交测试基础设施变更。随后进入 DEVELOP，实现并替换 planned 节点。
