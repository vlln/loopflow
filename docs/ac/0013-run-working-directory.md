---
title: loopflow AC-0013 — Run 显式工作目录
description: 验收 create_run 接受 working_directory、executor 子进程 chdir、文件观察目录正确、WebUI 创建入口与校验错误码
type: ac
status: active
created: 2026-07-24T05:30:00Z
---

# AC-025: Run 显式工作目录

验证 run 的工作目录从隐式进程 cwd 提升为显式属性后的全链路行为。详见 [ADR-0042](../adr/0042-run-working-directory.md) 和 [BR-044](../spec/0001-loopflow.md)。

## 正常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-025-N-1 | server 进程 cwd 为 `/A`，`/B` 为已存在目录 | `POST /api/v1/runs`，body 含 `working_directory: "/B"` | 返回 201；`run.json` 的 `working_directory` 为 `/B`；run 目录落在 `runs_root/lf_B/` 命名空间下 | 自动化 |
| AC-025-N-2 | 同 AC-025-N-1，loop 的 workflow 会在工作目录创建文件 | 等待 run 执行 | workflow 在 `/B` 内执行（创建的文件出现在 `/B`）；`file_changes.jsonl` 记录的是 `/B` 的变化，不是 `/A` 的 | 自动化 |
| AC-025-N-3 | WebUI 已打开，server cwd 为 `/A` | New Run 对话框填写 working directory `/B` 并启动 | run 创建成功且 `working_directory` 为 `/B`；留空时与现状一致（`/A`） | 自动化 |
| AC-025-N-4 | run 的 working_directory 为 `/B`，`/B/src/main.py` 为文本文件 | `GET /api/v1/runs/{run_id}/file?path=src/main.py` | 返回 200，body 含 `path`/`media_type`/`content`/`size`/`read_only` | 自动化 |
| AC-025-N-5 | 同 AC-025-N-4，WebUI 已打开该 Run 且有文件变化记录 | 在文件变化目录树中点击 `src/main.py` | 弹出只读预览，显示 `/B/src/main.py` 的当前内容 | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-025-B-1 | server 进程 cwd 为 `/A` | `POST /api/v1/runs`，body 不含 `working_directory` | 行为与现状完全一致：工作目录为 `/A`，向后兼容 | 自动化 |
| AC-025-B-2 | `/B` 为已存在目录 | `POST /api/v1/runs`，body 含 `working_directory: "B"`（相对路径） | 返回 422 `validation_failed`，details 指明 `not_absolute` | 自动化 |
| AC-025-B-3 | run 以 `working_directory: "/B"` 创建并失败 | 对该 run 执行 recover | recover 沿用 `/B` 执行；recover 请求体中的 `working_directory` 字段被拒绝或忽略，不覆盖原值 | 自动化 |
| AC-025-B-4 | run 的 working_directory 为 `/B` | `GET /api/v1/runs/{run_id}/file?path=../A/secret.txt`（resolve 后越出 `/B`） | 返回 403 `path_forbidden`；不返回文件内容 | 自动化 |
| AC-025-B-5 | run 的 working_directory 为 `/B`，`/B/blob.bin` 为二进制文件或超过 1 MiB | `GET /api/v1/runs/{run_id}/file?path=blob.bin` | 返回 422 `file_not_previewable`；不返回文件内容 | 自动化 |

## 异常场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-025-E-1 | `/nonexistent` 不存在 | `POST /api/v1/runs`，body 含 `working_directory: "/nonexistent"` | 返回 422 `validation_failed`，details 指明 `not_found`；不创建 run 目录 | 自动化 |
| AC-025-E-2 | `/etc/hostname` 是文件而非目录 | `POST /api/v1/runs`，body 含 `working_directory: "/etc/hostname"` | 返回 422 `validation_failed`，details 指明 `not_a_directory`；不创建 run 目录 | 自动化 |
| AC-025-E-3 | run 的 working_directory 为 `/B`，`/B/missing.txt` 不存在 | `GET /api/v1/runs/{run_id}/file?path=missing.txt` | 返回 404 `file_not_found` | 自动化 |

## 失败场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-025-F-1 | run 以 `working_directory: "/B"` 运行中 | 执行期间删除 `/B` | 文件观察器返回空快照、不阻塞 workflow；run 状态由 workflow 自身结果决定，不因观察失败而失败 | 自动化 |
