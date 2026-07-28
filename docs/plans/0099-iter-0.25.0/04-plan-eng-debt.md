---
title: Plan — 工程债：npm audit 修复 + 版本号单源化
description: 升级 vitest/coverage-v8 到 4.1.10 修复 brace-expansion 高危漏洞（BL-011）；__init__.py 用 importlib.metadata 读版本号替代硬编码（BL-013）
type: plan
status: pending
created: 2026-07-27T12:30:00Z
---

# Plan: 工程债 — npm audit + 版本号单源化

## 目标

两个独立的工程债，合并为一个 Plan 因为都是构建/配置层面：

1. **BL-011**：`@vitest/coverage-v8` 3.2.7 经 `test-exclude` → `glob` → `minimatch` → `brace-expansion` ≤5.0.7 引入 5 个 high 级别漏洞（DoS/OOM）。升级到 `4.1.10` 修复。

2. **BL-013**：版本号双写在 `pyproject.toml:3` 和 `src/loopflow/__init__.py:6`，手动同步易出错（0.25.0 release 时 commit message 先写成 v0.25.0 又改成 v0.24.2）。用 `importlib.metadata.version("loopflow")` 从已安装的包元数据读取，消除第二个硬编码源。

## 步骤

### BL-011：vitest 升级

1. **`web/package.json`** — 升级两个包

   ```json
   "@vitest/coverage-v8": "4.1.10",   // 从 3.2.7 升级
   "vitest": "4.1.10",                 // 从 3.2.7 升级（必须同 major）
   ```

2. **`npm install` + `npm audit`** — 验证漏洞清除

3. **`npx vitest run`** — 验证测试全绿（vitest 4.x 可能有 breaking change，需修复测试 API 调用）

4. **`npm run build`** — 验证前端构建正常

### BL-013：版本号单源化

1. **`src/loopflow/__init__.py:6`** — 替换硬编码版本

   ```python
   from importlib.metadata import version, PackageNotFoundError

   try:
       __version__ = version("loopflow")
   except PackageNotFoundError:
       __version__ = "0.0.0+dev"
   ```

2. **`tests/unit/test_smoke.py:21`** — 验证现有断言

   `assert loopflow.__version__ == version`（从 pyproject.toml 读取）。`importlib.metadata.version("loopflow")` 在已安装场景下返回 pyproject.toml 的版本号，断言自动通过。在开发模式（`pip install -e .`）下也有效。

3. **验证**：`.venv/bin/python -m pytest tests/unit/test_smoke.py -x -q` 全绿

## AC 覆盖

- 无新增 AC（工程债修复，不改变功能行为）
- AC-014-N-11（既有）：`GET /api/v1/system/meta` 返回的 version 与 `loopflow.__version__` 一致——单源化后仍满足

## Constraints

- vitest 4.x 的 breaking change 需评估：主要风险是 `describe`/`it`/`expect` API 变化、配置文件格式变化。如果测试大量 break，回退到 3.2.7 + `overrides` 强制 brace-expansion ≥5.0.8（npm 不推荐但可行）。
- `importlib.metadata` 是 Python 3.8+ 标准库，loopflow 最低支持 3.10，无兼容问题。
- 不改 `web/package.json` 的 `"version": "0.0.0"`（前端版本号独立于 Python release 版本，是有意设计）。

## Checkpoint

- `web/package.json`：vitest + coverage-v8 升级到 4.1.10
- `npm audit`：0 high
- `npx vitest run`：全绿
- `src/loopflow/__init__.py`：版本号从 `importlib.metadata` 读取
- `pytest tests/unit/test_smoke.py`：全绿

## 风险

- vitest 4.x 可能引入 breaking change 导致测试 break。缓解：先升级，跑测试，如果 break 少量则修复，如果大量则回退 + overrides 方案。
- `importlib.metadata.version()` 在未安装（直接 `python src/loopflow` 运行）时抛 `PackageNotFoundError`。fallback 到 `"0.0.0+dev"` 覆盖此场景。
