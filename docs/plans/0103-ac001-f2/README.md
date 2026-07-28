# 执行容器 0103 — AC-001-F-2 pi argv 进程测试（BL-048）

| 子任务 | 状态 |
|--------|------|
| AC-001-F-2 进程级回归测试（假 pi getopt 误判）+ agent manifest 回填 | done |

## 分支

`fix/0103-ac001-f2-pi-argv`（SYSTEM_TEST 严格模式前置修复，从 `develop` 拉出）

## 结果

- `tests/integration/test_cli.py::TestPiBackendArgv::test_ac001_f2_frontmatter_stripped_prompt_not_an_unknown_option`：假 pi（getopt 语义，`---` 开头 token 报 Unknown option + exit 1；否则输出合法 pi stream JSON）经 PATH 注入，走 CLI 单 agent 入口真实 spawn；断言 run done、exit_code=0、无 "Unknown option"。回归意义已双向验证（修复前 prompt 形状 → 红，修复后 → 绿）。
- `check-ac-manifest.py --profile agent` 严格模式 26 scenarios exit 0，AC-001-F-2 planned:: 消除。
- 全量 `tests/` 549 passed + 1 skipped。commit `ae721c0`。
