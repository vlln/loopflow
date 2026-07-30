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
| AC-025-N-3 | WebUI 已打开，server cwd 为 `/A` | New Run 对话框填写 working directory `/B` 并启动 | run 创建成功且 `working_directory` 为 `/B`；留空时框架创建 `run_dir/work` 隔离目录（ADR-0054） | 自动化 |
| AC-025-N-4 | run 的 working_directory 为 `/B`，`/B/src/main.py` 为文本文件 | `GET /api/v1/runs/{run_id}/file?path=src/main.py` | 返回 200，body 含 `path`/`media_type`/`content`/`size`/`read_only` | 自动化 |
| AC-025-N-5 | 同 AC-025-N-4，WebUI 已打开该 Run 且有文件变化记录 | 在文件变化目录树中点击 `src/main.py` | 弹出只读预览，显示 `/B/src/main.py` 的当前内容 | 自动化 |
| AC-025-N-6 | server 运行于 macOS，WebUI 打开 New Run 对话框 | 点击 Browse 按钮，在系统目录选择器中选中 `/B` | `POST /api/v1/system/pick-directory` 返回 200 `{"path": "/B"}`；对话框 working directory 输入被填充为 `/B` | 自动化（端点 subprocess mock） |

> 2026-07-26 追加（BL-020 / [ADR-0042 §5](../adr/0042-run-working-directory.md)）：CLI 暴露 `--work-dir` 参数，统一 workdir 概念（backend cwd = 产出目录）。CLI 路径不经过 REST API，`os.chdir` 直接在 CLI 进程内完成。新增 N-7、B-8、B-9、E-4、F-2 验证 CLI 路径。注意：CLI `--work-dir <path>` 对不存在路径执行 `mkdir -p`（创建），而 REST API 要求路径已存在（返回 422）——CLI 更宽松，符合命令行使用直觉。

### 正常场景（追加）

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-025-N-7 | CLI 进程 cwd 为 `/A`，无 `--work-dir` 参数 | `loop run hello --backend mock`（不传 `--work-dir`） | run 在 `/A` 执行；workflow 创建的文件出现在 `/A`；行为与 `cd /A && loop run` 一致（向后兼容） | 自动化 |

> 2026-07-27 追加（BL-009 / [ADR-0053](../adr/0053-web-directory-picker.md)）：Web 端跨平台目录浏览器替代 macOS-only osascript。新增 N-8 验证 Web 目录浏览器正常流程，修改 B-7 为非 macOS 平台使用 list-directory 端点。

### 正常场景（追加 2）

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-025-N-8 | WebUI 打开 New Run 对话框，server cwd 为 `/A`，`/A/sub` 为已存在子目录 | 点击 Browse → 模态框显示 `/A` 子目录列表 → 点击 `sub` → 点击 Select | working directory 输入填充为 `/A/sub`；`GET /api/v1/system/list-directory`（不传 path）返回 200 含 `sub`；`GET ...?path=/A/sub` 返回 200 | 自动化 |

### 边界场景（追加）

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-025-B-8 | CLI 进程 cwd 为 `/A` | `loop run hello --work-dir "" --backend mock` | 框架在 `run_dir/work` 下创建隔离工作目录并 chdir；workflow 创建的文件出现在 `run_dir/work` 而非 `/A` | 自动化 |
| AC-025-B-9 | `/B` 为已存在目录 | `loop run hello --work-dir /B --backend mock` | 框架 chdir 到 `/B`；workflow 创建的文件出现在 `/B`；run.json 不含 working_directory 字段（CLI 路径不写 REST 字段） | 自动化 |

### 异常场景（追加）

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-025-E-4 | `/tmp/lf-new-project` 不存在 | `loop run hello --work-dir /tmp/lf-new-project --backend mock` | 框架 `mkdir -p` 创建该目录并 chdir；run status=done，exit_code=0，stderr 无错误（CLI 路径创建不存在路径，与 REST API 的 422 not_found 不同） | 自动化 |

### 失败场景（追加）

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-025-F-2 | loop workflow 代码用相对路径（`Path("output.txt")`），`--work-dir /B` 已设置 | `loop run hello --work-dir /B --backend mock` | loop 函数不收 `work_dir` 参数；`Path("output.txt")` 解析为 `/B/output.txt`；agent 看到的 `Path.cwd()` 为 `/B` | 自动化 |

> 2026-07-27 追加（BL-026 / [ADR-0054](../adr/0054-webui-default-workdir-isolation.md)）：WebUI/API 未提供 `working_directory` 时，默认创建 `run_dir/work` 隔离目录而非 fallback 到 server cwd。修改 B-1 预期行为，新增 N-9、B-12、E-5、F-3 验证默认隔离路径。

### 正常场景（追加 3）

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-025-N-9 | server 进程 cwd 为 `/A` | `POST /api/v1/runs`，body 不含 `working_directory`，用 mock backend | 返回 201；`run.json` 的 `working_directory` 为 `{run_dir}/work` 绝对路径；run 目录落在 `runs_root/lf_A/` 命名空间下（按 server cwd 分组不变） | 自动化 |

## 边界场景

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-025-B-1 | server 进程 cwd 为 `/A`，run 已通过 N-9 创建 | 检查子进程行为 | 子进程 chdir 到 `run_dir/work`（非 `/A`）；`file_changes.jsonl` 的 observer 扫描 `run_dir/work` 而非 `/A`；agent 的 `Path.cwd()` 为 `run_dir/work` | 自动化 |
| AC-025-B-2 | `/B` 为已存在目录 | `POST /api/v1/runs`，body 含 `working_directory: "B"`（相对路径） | 返回 422 `validation_failed`，details 指明 `not_absolute` | 自动化 |
| AC-025-B-3 | run 以 `working_directory: "/B"` 创建并失败 | 对该 run 执行 recover | recover 沿用 `/B` 执行；recover 请求体中的 `working_directory` 字段被拒绝或忽略，不覆盖原值 | 自动化 |
| AC-025-B-4 | run 的 working_directory 为 `/B` | `GET /api/v1/runs/{run_id}/file?path=../A/secret.txt`（resolve 后越出 `/B`） | 返回 403 `path_forbidden`；不返回文件内容 | 自动化 |
| AC-025-B-5 | run 的 working_directory 为 `/B`，`/B/blob.bin` 是不在允许预览扩展名中的二进制文件 | `GET /api/v1/runs/{run_id}/file?path=blob.bin` | 返回 422 `file_not_previewable`；不返回文件内容 | 自动化 |
| AC-025-B-6 | server 运行于 macOS，用户在系统目录选择器中点击取消 | `POST /api/v1/system/pick-directory` | 返回 200 `{"path": null, "cancelled": true}`；WebUI 不改变输入框内容 | 自动化 |
| AC-025-B-7 | server 运行于非 macOS 平台 | `GET /api/v1/system/list-directory`（不传 path） | 返回 200，含 server cwd 的子目录列表；WebUI Browse 按钮始终可用，打开 Web 目录浏览器模态框（ADR-0053） | 自动化 |
| AC-025-B-10 | `/nonexistent` 不存在 | `GET /api/v1/system/list-directory?path=/nonexistent` | 返回 404 `file_not_found` | 自动化 |
| AC-025-B-11 | `/etc/hostname` 是文件而非目录 | `GET /api/v1/system/list-directory?path=/etc/hostname` | 返回 422 `validation_failed`，details 指明 `not_a_directory` | 自动化 |

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

### 边界场景（追加 2）

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-025-B-12 | 旧 run（ADR-0054 前创建），`run.json` 的 `working_directory` 为 server cwd `/A` | 对该 run 执行 recover | recover 沿用 `/A`（从 `run.json` 读取），不创建 `run_dir/work` | 自动化 |
| AC-025-B-13 | run 的 working_directory 为 `/B`，`/B/large.txt` 是超过 1 MiB 的 UTF-8 文本 | `GET /api/v1/runs/{run_id}/file?path=large.txt` | 返回 422 `file_not_previewable`；不返回 content/raw_url | 自动化 |

### 异常场景（追加 2）

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-025-E-5 | server 进程 cwd 为 `/A`，`run_dir/work` 父目录不可写（权限不足） | `POST /api/v1/runs`，body 不含 `working_directory` | 创建 `run_dir/work` 时 OSError，返回 500 `atomic_write_failed`；不启动子进程 | 自动化 |

### 失败场景（追加 2）

| 编号 | 前置条件 | 操作步骤 | 预期结果 | 验证方式 |
|------|----------|----------|----------|----------|
| AC-025-F-3 | server cwd `/A` 下有外部进程正在修改文件（如其他 Agent 修改 `src/runner.py`），run 未提供 `working_directory` | `POST /api/v1/runs`，body 不含 `working_directory`，等待 run 执行 | `file_changes.jsonl` 不记录 `src/runner.py` 的变化（observer 扫描 `run_dir/work`，不是 `/A`）；只记录 run agent 在 `run_dir/work` 内创建/修改的文件 | 自动化 |
