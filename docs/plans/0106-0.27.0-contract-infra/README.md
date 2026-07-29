# 执行容器 0106 — 0.27.0 增量契约测试基建

| 子任务 | Plan | Report | 状态 |
|--------|------|--------|------|
| AC manifest、Interface schema 与 mock 能力增量 | [01-plan-contract-infra.md](01-plan-contract-infra.md) | [01-report-contract-infra.md](01-report-contract-infra.md) | done |

## 分支

`test/0106-0.27.0-contract-infra`（从 `develop` 拉出）

## 范围

- Recovery manifest 覆盖 AC-023-N-6~F-5
- 新增 0.27.0 profile 覆盖 AC-033~035
- Interface v18 的 Intervention、FilePreview、DeclaredArg 与 append_prompt schema fixture
- 仅对新增规则做正反向自证
