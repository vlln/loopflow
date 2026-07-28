## 写作要求

- 每条 AC 编号格式：`AC-xxx-N/B/E/F-n`（N=正常，B=边界，E=异常，F=失败）
- 前置条件必须可复现（如"数据库中存在用户 U001"）
- 操作步骤必须可执行（如"POST /api/order，body={...}"）
- 预期结果必须可验证（如"返回 201，body 含 order_id"）
- 只写正常流程的 AC 属于无效 AC

## 状态说明

| 状态 | 含义 |
|------|------|
| draft | 编写中 |
| proposed | 编写完成，待出口把关审查 |
| active | 审查通过，当前生效 |

## 文档列表

| 编号 | 标题 | 状态 | 覆盖模块 |
|------|------|------|---------|
| [0003](0003-agent-layer.md) | Agent 层抽象 AC | active | Agent 类、能力 marshalling、runtime 薄封装、向后兼容、ACP 后端 loop 端到端、parse_agent 剥离 frontmatter（BL-017/018/019） |
| [0004](0004-scheduling.md) | 调度 AC | active | dispatch, queue, loop.md, resource lock |
| [0010](0010-webui.md) | 本地 WebUI 控制台 AC | active | Runs, Phase occurrence, SSE, Loops, Backends, WebUI, call/occurrence 显示简化（BL-021） |
| [0011](0011-recovery-intervention.md) | 可靠恢复、可靠取消与人工介入 AC | proposed | recover retry/continue, cancellation, intervention, CLI 内联应答 + 无人值守（BL-044/045） |
| [0012](0012-file-changes.md) | 工作目录文件变化观察 AC | active | file_changes.jsonl, phase 边界快照 diff, WebUI 文件变化展示 |
| [0013](0013-run-working-directory.md) | Run 显式工作目录 AC | active | working_directory, create_run, executor chdir, WebUI 创建入口, CLI --work-dir（BL-020） |
| [0014](0014-single-agent-run.md) | 单 agent 运行入口 AC | proposed | loop run --agent, --prompt/--prompt-file/--param, output schema 自动应用（BL-047） |
