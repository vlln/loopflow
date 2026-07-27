# Backlog

工程需求池。DESIGN 阶段的迭代候选只能从这里拉取；选定后状态改为 `planned` 并记录关联迭代。

状态值：`candidate`（待评估）→ `planned`（已排入迭代）→ `done`（已闭环）/ `dropped`（放弃，需注明原因）

| 编号 | 标题 | 描述 | 来源 | 状态 | 关联迭代 |
|------|------|------|------|------|---------|
| BL-001 | 失败分类驱动的重试/续接策略 | 将 agent 调用失败分类（auth/quota、poisoned、transient、task），按类别决定重试、会话续接（continue）或直接失败，替代统一退避重试 | loopany-platform 调研 2026-07-25 | done | 0.21.0 |
| BL-002 | 失败熔断 + 告警节流 | 连续失败达到阈值自动暂停；失败提示只在状态转变和周期性提醒时出现，防告警疲劳 | loopany-platform 调研 2026-07-25 | done | 0.21.0 |
| BL-003 | reconcile 失联宽限期 | 失联 ≠ 失败：run 失联后进入宽限期，宽限期内恢复可调和为成功，避免笔记本睡眠等场景误判 | loopany-platform 调研 2026-07-25 | done | 0.21.0 |
| BL-004 | 调度语义 deferred/supersede/misfire | 队列中等待的任务被取代标记 skipped、条件不满足挂起 deferred、错过触发补发，均不计为失败 | loopany-platform 调研 2026-07-25 | done | 0.21.0 |
| BL-005 | evolve run 自我进化 | 每 N 次 run 触发一次用 run 历史重写 loop 本身的 run（收紧 brief、折叠机械步骤）。业务层 vs 产品层未定 | loopany-platform 调研 2026-07-25 | candidate | — |
| BL-006 | loop 嵌套编排 | workflow 嵌套/组合的下一个大特性，方向未想好 | loopany-platform 调研 2026-07-25 | candidate | — |
| BL-007 | web profile manifest 漂移修复 | 以 test 容器补齐 web profile AC manifest | 0.20.0 发布评估 | candidate | — |
| BL-008 | loop args schema 服务端校验 | Web/API 侧对 loop args 做 schema 校验 | 0.20.0 发布评估 | candidate | — |
| BL-009 | 非 macOS 目录选择器 | Web UI 目录选择器在非 macOS 平台的适配 | 0.20.0 发布评估 | candidate | — |
| BL-010 | AC-010-N-2/E-2 契约漂移裁决 | AC 文本期望 loop.md 缺失/坏 YAML 时回退 workflow.py meta，但 ADR-0031 后实现为强制 loop.md 缺失即跳过；需 DESIGN 裁决对齐文档或实现 | 0081 scheduling profile 落地时发现 | done | 0.21.0 |
| BL-011 | npm audit 既有失败修复 | brace-expansion 经 @vitest/coverage-v8 链 5 high，中断 mr-gate 链 | 0081 mr-gate 验证时发现 | candidate | — |
| BL-012 | SSE file_changes OSError 未按 topic 隔离 | AC-016-F-3 实证发现：fc 读取 OSError 落入 server 通用 except，发无 topic 的 stream_error，与 AC-016-E-3 的 topic 隔离行为不一致；需裁决是缺陷还是可接受形态 | 0086 清理时发现 | candidate | — |
| BL-013 | 版本号单源化 | 版本号双写（pyproject.toml + src/loopflow/__init__.py）易不同步，0.21.0 release 冒烟时暴露 | 0.21.0 复盘 | candidate | — |
| BL-014 | 采用官方 Python ACP SDK 替换手搓 ACP 管道 | acp.py/acp_backend.py 手搓 JSON-RPC 是未验证 stub（runtime 从不传 transport=acp，ACP 路径生产里是死的）；用官方 agent-client-protocol 替换协议管道，保留 loopflow 自己的 session/recovery/queue；CLI 保留为主传输，ACP 成为真正可用的可选路径 | 0.21.0 后架构调研（acpx 对比） | done | 0.22.0 |
| BL-015 | agent-client-protocol 划为可选 extra [acp] | 0.22.0 实现阶段放主依赖区，ADR-0049 §8 定位为可选 extra 未落地；默认安装不应含 pydantic | 0.22.0 复盘 | candidate | — |
| BL-016 | grok ACP `_meta` system prompt 在 SDK 路径的等价处理 | SDK session/new 不接受 _meta，0089 改走 prompt 文本拼接，需验证 grok 行为不回归 | 0.22.0 复盘 | candidate | — |
| BL-017 | render_template 模板变量转 str | `_replace` 返回 `str(value)`，防 integer/None 模板变量致 `re.sub` TypeError（如 `{{ breadth }}` 传 int） | deep-research 实测 2026-07-26 | done | 0.23.0 |
| BL-018 | parse_agent 剥离 frontmatter | body 只含 markdown 正文（不含 frontmatter），避免 system prompt 含元数据，且 CLI backend（pi）把 prompt 作 argv 时 `---` 被当 unknown option | deep-research 实测 2026-07-26 | done | 0.23.0 |
| BL-019 | pi backend 用 text_end 消息级 event | `_parse_line` 取 `text_end` 的完整 content，弃 `text_delta`（token 级），修 `_extract_text` `"\n".join` 在流式 delta 间插 `\n` 破坏 JSON 字符串值 | deep-research 实测 2026-07-26 | done | 0.23.0 |
| BL-020 | CLI `--work-dir` 统一工作目录 | `loop run --work-dir [path|""|缺省]`，框架 chdir 到 workdir；loop 不处理工作目录，agent 用相对路径（当前目录）。统一 backend cwd 与产出目录，消除 run_dir/work 冗余 | deep-research 实测 2026-07-26 | done | 0.23.0 |
| BL-021 | webUI call/occurrence 显示简化 | call-list 主显 call_id（逻辑编号），session 降 tooltip；节点 "×N"、详情 "第 N 次执行"、EventTimeline "N 个事件"——消除 call_id 重复（session 含 call_id 又单独显示）+ occurrence/events 措辞区分 | devloop DESIGN 2026-07-26 | done | 0.23.0 |
