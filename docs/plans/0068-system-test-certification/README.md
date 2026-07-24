# 0068 SYSTEM_TEST 认证

对应阶段：`SYSTEM_TEST`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [系统测试认证](01-plan-system-test-certification.md) | [Report](01-report-system-test-certification.md) | done |

## 范围

- 在 `develop` 上对 0.19.0 后续修复与 WebUI 整理进行系统级验证。
- 覆盖 0065 boolean choice 兼容、0066 WebUI primitives、0067 `gork` 误拼写 backend 删除。
- 复核 AC manifest、Python 全量测试、前端测试、浏览器测试和 wheel smoke。
- 对失败进行分类并给出是否可进入 RELEASE 的结论。

## 非范围

- 不新增 feature/refactor/fix 代码。
- 不创建 release 分支或 tag。
