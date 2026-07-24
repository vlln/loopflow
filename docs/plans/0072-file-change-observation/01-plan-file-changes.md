---
title: File Change Observation Implementation Plan
description: 实现 phase 边界文件变化快照 diff、file_changes.jsonl 和 WebUI 展示
type: plan
status: done
created: 2026-07-23T15:00:00Z
---

# Goal

实现 ADR-0039 的文件变化观察层。phase() 调用时快照 diff，写入 file_changes.jsonl（含 seq），通过 SSE file_changes topic 推送，WebUI 展示。替换 AC-024 的 planned 节点。

# Acceptance

1. phase() 调用时对 pwd 递归扫描快照，与上一快照 diff。
2. diff 结果追加到 file_changes.jsonl，含 seq（严格递增）、phase、phase_id、ts、changes。
3. changes 含 path/action(created/modified/deleted)/size/prev_size。
4. meta.file_observation.enabled=false 时不创建 file_changes.jsonl。
5. meta.file_observation.exclude 规则排除匹配文件。
6. file_changes 不写入 events.jsonl，不参与重放。
7. worktree 隔离的 Agent 变化不纳入 pwd 快照。
8. WebUI Phase 详情下方显示文件变化列表。
9. SSE file_changes topic 推送（依赖 0070 的多 topic transport）。
10. AC-024 manifest planned 节点被真实测试替换。

# Steps

1. 新建 file_observation 模块：snapshot scan、diff、exclude 匹配。
2. runtime phase() 调用时触发快照 diff，追加 file_changes.jsonl（含 seq）。
3. application service 增加 file_changes 查询读模型。
4. meta.file_observation 配置解析。
5. WebUI types/api 增加 file changes 数据结构。
6. WebUI Phase 详情组件增加文件变化列表渲染。
7. SSE file_changes topic 推送接入（依赖 0070）。
8. 替换 AC-024 manifest planned 节点。
9. 运行 Python/Web/manifest 验证。
10. 写 Report、标记 done 并提交。

# Exit

0072 done 后，文件变化观察功能完整可用。
