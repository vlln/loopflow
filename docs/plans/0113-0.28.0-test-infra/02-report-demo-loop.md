---
title: BL-057/058 demo loop + SYSTEM_TEST 真实链路黑盒 — Report
description: demo loop 资产与端到端黑盒测试记录
type: report
status: complete
created: 2026-08-03T00:00:00Z
---

# Report — BL-057/058 demo loop + 黑盒盲区

## 结论

已闭环。新增 demo loop 资产与真实链路黑盒测试，补上 0.27.1 复盘确认的 SYSTEM_TEST 盲区（AC-033/AC-023 此前仅 fixture/mock 集成覆盖）。

## 产出

### demo loop 资产（`tests/agent_support/demo_loop/`）

| 文件 | 内容 |
|------|------|
| `loop.md` | name=demo，开启 file_changes 观察 |
| `workflow.py` | 阶段一 `agent("python3 <loop>/gen_assets.py")`；阶段二 `intervene("approve-chart", options=[批准, 拒绝])` 并写入 state |
| `gen_assets.py` | 生成 1x1 红 PNG（68B）+ 最小单页 PDF（220B），写入 cwd |
| `agents/default.md` | assets agent 定义 |

### 黑盒测试（`tests/e2e/test_demo_loop_blackbox.py`）

真实链路端到端（不调付费 Agent，可入 CI）：
1. 真实 CLI `loopflow run demo --mock bash --work-dir ""` → run 进入 `waiting_input`。
2. **AC-033**：assets agent 真实生成 `chart.png`/`report.pdf`（文件头断言）；web preview 返回 `encoding=raw` + raw_url；raw 端点返回正确 Content-Type（image/png、application/pdf）与完整 bytes。
3. **AC-023**：interventions API 列出 pending 请求；POST response 后 run 恢复 replay 到 `done`，`state.answer == "批准"`。

## 自证

| 项 | 结果 | 证据 |
|----|------|------|
| 黑盒测试 | 1 passed | `tests/e2e/test_demo_loop_blackbox.py` |
| e2e 全量 | 23 passed | `tests/e2e` |
| 全量测试 | 693 passed, 1 skipped | `tests/` |
| MR 门禁 | 全绿 | 覆盖率 83.45%（要求 59%） |

## 证据路径

- commit `c78fe2e`（test/e2e）
- 盲区来源：0108 REPORT（AC-033/AC-023 仅 fixture 覆盖）、0.27.1 事件串线缺陷
