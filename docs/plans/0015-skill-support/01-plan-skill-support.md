---
title: Skill Support Implementation
description: 实现 ADR 0015 — requires.skills 的 prompt 注入 + 原生支持双轨策略
type: plan
status: pending
created: 2026-07-10T10:30:00Z
---

# Plan: Skill Support

## 范围

实现 agent skill 声明、查找和注入。不涉及 skill 下载、版本管理。

## 步骤

### 1. Skill 发现模块 (`src/loopflow/skills.py`)

- `find_skill(name: str) -> dict | None`：按 `~/.agents/skills/` → `~/.loopflow/skills/` 查找 skill 目录
- `parse_skill(skill_dir: Path) -> dict`：解析 `SKILL.md` 的 frontmatter
- `build_skill_prompt(skill_names: list[str]) -> str`：构建 prompt 注入段（名称+描述+路径）

### 2. Runtime 集成 (`src/loopflow/runtime.py`)

- `agent()` 中，当 `requires.skills` 非空时：
  - 解析 skill 列表
  - 如果后端支持原生 skill → 不注入（保持现有行为）
  - 否则 → 调用 `build_skill_prompt()` 注入到 system prompt

### 3. 后端适配

- `cli_backend.py`：`_apply_requires_to_cmd` 保持不变（已有 `_skill_flag` 的后端继续使用）
- 新增 `backend.supports_native_skills() -> bool` 方法，供 runtime 判断是否需要 prompt 注入

### 4. 测试

- Unit: skill 查找、解析、prompt 构建
- Unit: runtime 集成（有 skill 声明的 agent 调用）
- E2E: bio-reproducer 使用 `requires.skills` 声明 `paperutils`

### 5. bio-reproducer 更新

- reader agent 的 `requires.skills` 添加 `paperutils`
- 创建 `~/.loopflow/skills/paperutils/SKILL.md`（从现有 paperutils 项目提取）

## 关联

- ADR 0015
- Spec v4 BR-013