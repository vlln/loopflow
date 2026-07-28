# 执行容器 0100 — 0.25.1 Patch

| 子任务 | Plan | Report | 状态 |
|--------|------|--------|------|
| BL-034 远程 run 文件预览失败 | [01-plan-bugfixes.md](01-plan-bugfixes.md) | [01-report-bugfixes.md](01-report-bugfixes.md) | done |
| BL-035 Events 重复渲染 | 同上 | 同上 | done |
| BL-036 后端显示为 unknown | 同上 | 同上 | done |
| BL-037 File changes 文件夹不可折叠 | 同上 | 同上 | done |
| BL-038 Loops 页面混入运行时状态 | 同上 | 同上 | done |
| BL-039 切换 Runs 时卡顿 | 同上 | 同上 | done |
| BL-040 Backends API 对 missing 后端调用 _make_backend | 同上 | 同上 | done |
| BL-041 切换页面卡顿 + missing catch | 同上 | 同上 | done |

## 分支

`fix/0251-bugfixes`（从 `develop` 拉出）

## 测试

- Python: 520 passed, 1 skipped
- Vitest: 42 passed
- Playwright: 13 passed, 2 skipped
