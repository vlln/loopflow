# 0048 SYSTEM_TEST 发布前认证

对应阶段：`SYSTEM_TEST`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [系统测试认证](01-plan-system-test-certification.md) | 待创建 | pending |

## 范围

- 在 `develop` 上执行系统级门禁，而非新增业务功能
- 复核全局 AC manifest 与 recovery strict manifest
- 运行 MR gate、前端、浏览器和 wheel smoke
- 对所有失败进行分类：基建缺陷、设计缺陷、局部 bug、外部环境问题
- 判定是否存在阻塞级缺陷，以及是否可进入 RELEASE

## 非范围

- 不新增 feature/refactor/perf 代码
- 不修改 AC/Spec/ADR 契约，除非系统测试证明存在设计缺陷并退回 DESIGN
- 不创建 release 分支或 tag；release 动作由后续 RELEASE 执行容器负责
