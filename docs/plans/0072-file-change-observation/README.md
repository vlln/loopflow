# 0072 工作目录文件变化观察

对应阶段：`DEVELOP`。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [文件变化观察层实现](01-plan-file-changes.md) | [Report](01-report-file-changes.md) | pending |

## 背景

ADR-0039 已 accepted。phase 边界快照 diff 追踪工作目录文件变化，独立 file_changes.jsonl 持久化，通过 SSE file_changes topic 推送。

## 范围

- phase() 调用时对 pwd 拍摄快照并与上一快照 diff
- file_changes.jsonl 写入（含 seq 序号）
- meta.file_observation.enabled / exclude 配置
- application service replay_file_changes 查询
- WebUI Phase 详情下方文件变化列表渲染
- SSE file_changes topic 推送（依赖 0070）

## 非范围

- 不实现行级 diff
- 不追踪 worktree 内部变化
- 不引入 fs watcher 依赖
- 不实现 SSE transport 重构（属于 0070）

## 依赖

- 0070 必须先完成（SSE file_changes topic 依赖多 topic transport）
