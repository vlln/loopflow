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
| [0010](0010-webui.md) | 本地 WebUI 控制台 AC | active | Runs, AgentGraph/Call, SSE, Loops, Backends, WebUI |
| [0011](0011-recovery-intervention.md) | 可靠恢复、可靠取消与人工介入 AC | active | recover retry/continue, Agent intervention 协议与并行多 session 恢复（BL-046） |
| [0012](0012-file-changes.md) | 工作目录文件变化观察 AC | active | file_changes.jsonl, Agent Call 完成边界快照 diff, WebUI 文件变化展示 |
| [0013](0013-run-working-directory.md) | Run 显式工作目录 AC | active | working_directory, 文件预览边界, WebUI 创建入口, CLI --work-dir（BL-020/051） |
| [0014](0014-single-agent-run.md) | 单 agent 运行入口 AC | active | loop run --agent, --prompt/--prompt-file/--param, output schema 自动应用（BL-047） |
| [0015](0015-iteration-0.27.0.md) | 0.27.0 用户输入与二进制预览 AC | active | 图片/PDF raw 预览、append_prompt、declared args 契约符合性（BL-051/052/054） |
