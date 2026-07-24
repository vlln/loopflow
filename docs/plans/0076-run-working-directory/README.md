# 0076 Run 显式工作目录与观察语义

对应阶段：`DEVELOP`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [Run 显式工作目录与观察语义](01-plan-run-working-directory.md) | [Report](01-report-run-working-directory.md) | done |

## 范围

- 实现 ADR-0042：create_run 接受 `working_directory`，executor 子进程 chdir，recover 沿用
- 实现 ADR-0043：observer 基线快照（seed），首个 phase 只记真 diff
- 实现 BR-046：`GET /runs/{run_id}/file` 只读端点 + WebUI 文件预览
- WebUI：New Run 对话框 working directory 输入；文件树点击预览
- 测试：AC-025 全场景、AC-024-B-1/B-8 重映射、前端对话框与预览测试

## 非范围

- 不改 ADR-0039/0041 已冻结内容
- 不做 shell-out wrapper（ADR-0042 已评估暂缓）
