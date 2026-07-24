---
title: Run 显式工作目录与观察语义 Report
description: ADR-0042 显式工作目录、ADR-0043 基线快照、BR-046 文件预览实现结果留档
type: report
status: done
created: 2026-07-24T06:00:00Z
---

# Summary

三个方向全部按冻结契约实现并验证通过：run 显式工作目录（create_run 校验 + 子进程 chdir + recover 沿用）、文件观察基线快照（seed，首个 phase 只记真 diff，实现向 AC-024-B-1 文档语义对齐）、run 工作目录文件预览（只读端点 + WebUI 目录树点击预览）。

# Changes

| 层 | 内容 |
|----|------|
| `application/web.py` | create_run 接受并校验 `working_directory`（`{"reason": "not_absolute"/"not_found"/"not_a_directory"}` → 422，先于 executor.start）；`preview_run_file()` 复用 LoopRepository.preview 判定逻辑（403/404/422）；recover 拒绝 working_directory 覆盖；rerun 透传原目录 |
| `application/execution.py` | `BackgroundRunExecutor.start()` 接受 working_directory（缺省进程 cwd）；子进程入口 `os.chdir()`；run.json 持久化 chdir 后权威路径；observer 初始化后立即 `seed()` |
| `infrastructure/file_observation.py` | 新增 `seed()`；observe() 无基线时首快照即基线、不产生记录（替换"全量 created"特判） |
| `infrastructure/web_storage.py` | `RunRepository.resolve_working_directory()`（run.json 优先、runs_index 兜底，仅返回绝对且存在的目录） |
| `presentation/web/server.py` | `GET /runs/{run_id}/file?path=` 路由（复用既有错误 dispatch） |
| `web/` | NewRunDialog 工作目录输入（留空不带字段）；`api.runFile()`；目录树文件行可点击；`RunFilePreviewDialog`（loading/error/done 三态，404/403/422 友好文案） |

# AC Results

| AC | 结果 | 测试 |
|----|------|------|
| AC-025-N-1 | [PASS] | `test_create_run_with_explicit_working_directory` + `test_background_executor_honors_explicit_working_directory`（lf_B 命名空间/run.json/runs_index） |
| AC-025-N-2 | [PASS] | `test_run_executes_and_observes_in_explicit_working_directory`（子进程端到端：/B 内执行、file_changes 记录 /B 变化、既有文件不算 created） |
| AC-025-N-3 | [PASS] | 前端 `AC-025-N-3`（对话框带/不带字段两段断言） |
| AC-025-N-4 | [PASS] | `test_run_file_preview_returns_text_content` |
| AC-025-N-5 | [PASS] | 前端 `AC-025-N-5`（目录树点击 → 预览对话框显示内容） |
| AC-025-B-1 | [PASS] | `test_create_run_without_working_directory_keeps_default` + 既有 `test_background_executor_uses_shared_target` |
| AC-025-B-2 | [PASS] | `test_create_run_rejects_relative_working_directory`（422 not_absolute，无 run 目录） |
| AC-025-B-3 | [PASS] | `test_recover_rejects_working_directory_override` + `test_recover_reuses_persisted_working_directory` |
| AC-025-B-4 | [PASS] | `test_run_file_preview_rejects_path_escape`（`../` 与绝对路径均 403） |
| AC-025-B-5 | [PASS] | `test_run_file_preview_rejects_binary_and_oversized`（二进制与 >1 MiB 均 422） |
| AC-025-E-1/E-2 | [PASS] | `test_create_run_rejects_nonexistent_working_directory` / `..._file_as_working_directory`（E-2 用 tmp 文件等价替代 /etc/hostname，可移植） |
| AC-025-E-3 | [PASS] | `test_run_file_preview_missing_file_and_unknown_run` + 前端 deleted 文件 404 友好提示 |
| AC-025-F-1 | [PASS] | 单元级等价 `test_deleted_working_directory_does_not_block_observation`（目录删除后空快照不抛异常；真实删除 cwd 的端到端平台风险高、收益低，未做） |
| AC-024-B-1 | [PASS] | 重映射 `test_first_observe_establishes_baseline_no_record`（实现向文档语义对齐） |
| AC-024-B-8 | [PASS] | `test_first_phase_modifies_preexisting_file_marks_modified_with_baseline_prev_size` |
| AC-024-N-8 | [PASS] | REST 记录测试 + 前端 per-phase 切换测试（0074 已交付机制） |

# Verification Results

| 层 | 结果 |
|----|------|
| Python 全量 | 401 passed, 1 skipped（基线 385 → 401） |
| AC-024 manifest strict | 0 错误，20 cases；`test_strict_manifest_has_no_planned_nodes` 通过 |
| recovery profile manifest | ok（55 scenarios） |
| 前端 vitest | 24 passed（19 → 24，原有用例未破坏） |
| 前端 typecheck / build | clean / 成功，静态资源已同步 |
| Playwright e2e | 10 passed, 2 skipped |

# Notes

- 422 错误 details 形状定为 `{"reason": "..."}`（契约未定键名）。
- `preview_run_file` 复用 `LoopRepository.preview`，403 文案仍写 "within the Loop"（仅文案，code 与行为正确；通用化需小重构 web_resources.py，留给后续）。
- web profile（AC-014..019）manifest 检查存在**预先失败**（断言漂移），与 0076 无关，未越界处理；建议在 SYSTEM_TEST 或后续容器分类。
- macOS 上 run.json 的 working_directory 为 chdir 后 resolved 形式（与 append_run_index 行为一致）。
