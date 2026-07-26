---
title: 框架健壮性修复 Plan
description: BL-017/018/019 三处框架层 bug 修复（render_template str 化 / parse_agent 剖 frontmatter / pi text_end），uv.lock 同步
type: plan
status: done
created: 2026-07-26T09:00:00Z
---

# Goal

修复 0.23.0 迭代 DESIGN 冻结的三个框架层 bug（BL-017/018/019），使三后端（kimi/pi/pi-acp）实测端到端跑通 deep-research。代码已执行并验证，本 Plan 记录已执行计划。

# Constraints

- 不改 deep-research loop 代码（`loop-library/loops/deep-research`）：bug 在框架层，loop 只是暴露器
- 代码不返工：三处均为最小定点修复，不做附带重构
- work_dir 传递链冗余删除不纳入本容器（见 0092）；本分支只含 agent_def/repository/pi/uv.lock
- 修复以三后端实测端到端 + unit 364 为验收，不新增 AC 场景

# Steps（已执行）

1. 建 `docs/plans/0091-framework-robustness/`（README + 本 Plan）
2. 分支 `fix/0091-framework-robustness` 从 develop
3. BL-017：`agent_def.py` `render_template._replace` 返回 `"" if value is None else str(value)`（原直接 `return kwargs[name]`，遇 int/None 时 re.sub 抛 TypeError）
4. BL-018：`repository.py` `parse_agent` 取 `body = parts[2].strip()`（原 `content.strip()` 含 frontmatter，prompt 以 `---` 开头被 pi 误解析为未知选项）
5. BL-019：`pi.py` `_parse_line` 改判 `text_end` 事件、返回 `event.get("content", "")`（原 `text_delta` token 片段，`_extract_text` 的 `"\n".join` 在 JSON 字符串值内插入裸 `\n` 破坏流式 JSON）
6. chore：uv.lock loopflow 版本 0.21.0 → 0.22.0
7. 验证：`pytest tests/unit` + 三后端实测 deep-research
8. Report + README done
9. commit 拆分：fix（1ad12d4）+ chore（e7dda0c）

# Acceptance

- `pytest tests/unit -q` 364 passed，零回归
- kimi 后端实测 deep-research：4 phase 全走通，24 claim 通过，report.md 产出
- pi 后端实测 deep-research：修 text_end 后跑通，24 claim
- pi-acp 后端实测 deep-research：ACP 模式跑通，24 claim
- `git diff develop..fix/0091-framework-robustness --stat` 只含 agent_def/repository/pi/uv.lock

# Checkpoint

- unit 364 passed（定点修复不破坏既有契约）
- 三后端实测端到端 deep-research（kimi/pi/pi-acp 各 24 claim）—— BL-019 修复前 pi 跑不通
- 分支隔离确认：diff 只含四个目标文件，无 work_dir 传递链改动泄漏

# Exit

全部 Acceptance 通过，写 Report，由用户合回 develop（--no-ff），不合并分支。
