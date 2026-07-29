---
title: 0.27.0 增量设计 Report
description: BL-051/046/052/054 的 Spec、AC、ADR、Interface 契约与独立审查、BL-046 spike 证据
type: report
status: complete
created: 2026-07-29T11:24:49Z
---

# Report: 0.27.0 增量设计

## 结果

| Checkpoint | 结果 | 证据 |
|------------|------|------|
| Spec v18 增量契约 | PASS | [Spec](../../spec/0001-loopflow.md) proposed；独立审查 PASS；commits `142fb14`、`4deb19a` |
| AC 四场景与可测试 oracle | PASS | [AC-0011](../../ac/0011-recovery-intervention.md)、[AC-0013](../../ac/0013-run-working-directory.md)、[AC-0015](../../ac/0015-iteration-0.27.0.md) proposed；独立审查 PASS；commit `48bd763` |
| BL-046 ADR 与技术验证 | PASS | [ADR-0057](../../adr/0057-agent-intervention-protocol.md) proposed；独立审查 PASS；commit `a90e0dc` |
| Web API Interface | PASS | [Interface 0001](../../interface/0001-web-api.md) proposed；独立审查 PASS；commit `4786ffc` |
| 权威文档冻结 | PENDING HUMAN | 尚未 promote；等待阶段末批量确认 |

## 关键设计结论

- BL-046 只在 prepared capabilities 同时具备 `resume_session` 和 `durable_session_id` 时宣告 Agent waiting_input 协议；pending 前还要求本次 Call 的非空 session_id 已落盘，不允许新 session 静默重跑。
- 业务输出、goal 正常输出与 framework control 使用互斥联合类型；Agent request 不接受 default/timeout。回答按 request group/index 恢复到原 session，并支持 parallel 多 continue targets。
- BL-051 冻结文本 1 MiB、图片/PDF 50 MiB、固定 MIME、preview `encoding=raw/raw_url`、raw 原子读取和 `file_read_failed`。
- BL-052 冻结 `--append-prompt` / `append_prompt`，UTF-8 64 KiB，作为不受信任 user prompt，写入 execution_options 和 input digest，recover 不可覆盖。
- BL-054 复用既有顶层 loop.md `args` 契约，仅在 loop.md 不存在时读取 workflow.py `meta.args`；本轮是符合性回归，不引入第二种格式。

## Spike

保留分支：`spike/0105-agent-intervention-capabilities`，commit `6eb383f6fbeb22fbb21f5e08005ed837392976e1`，不合并。

```bash
uv run python spikes/0105_agent_intervention_capabilities.py
```

环境：Python 3.14.6（项目约束 3.10+）、agent-client-protocol 0.11.0、jsonschema 4.26.0。执行 exit 0：

```text
ACP_PREFLIGHT PASS {"session_new": 1, "transport_start": 1}
SCHEMA_UNION PASS {"accepted": 3, "rejected": 5}
MULTI_TARGET PASS [{"call_id": "call-a", ...}, {"call_id": "call-b", ...}]
```

## 审查发现与处置

- 明确 storage group 与 actual working_directory 的五种 CLI/Web 输入映射，消除 Web 缺省隔离目录的循环定义，并保留 CLI 显式 work-dir 的既有分组行为。
- 将 AC 中三处“正常”模糊 oracle 改为精确输出、HTTP 响应或 Run 终态；补齐 incomplete/duplicate batch 与 recover override 的确定结果。
- Interface 将 legacy Intervention 归一化为单一 read model，batch response 保持 `any` 以支持 workflow schema/null，同时 Agent response 仍约束为非空 string。
- `agent_intervention_not_supported` 明确为异步 Call/Run failure code，不误映射为同步 HTTP 409。

## 门禁边界

DESIGN 未编写业务代码，除 ADR spike 外未执行 DEVELOP 测试。Spec/AC/Interface 均保持 proposed，ADR-0057 保持 proposed；收到人类批量确认前不得 promote，也不得进入 TEST_INFRA。
