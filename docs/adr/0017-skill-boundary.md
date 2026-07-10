---
title: Skill Declaration Boundary — agent declares WHAT, environment declares WHERE
description: 修正 ADR 0015：移除 SKILL.md 的 path/source 字段，skill 安装由环境管理器负责
type: adr
status: accepted
created: 2026-07-10T14:00:00Z
---

# ADR 0017: Skill Declaration Boundary

## 动机

ADR 0015 在 SKILL.md 中定义了 `path` 和 `source` 可选字段，用于指定 skill 的安装位置和来源。这违反了关注点分离：

- **Agent 声明 WHAT**：需要什么 skill（`requires.skills: [paperutils]`）
- **环境声明 WHERE**：从哪安装（`pixi.toml` 或 `environment.yml`）

`path`/`source` 是 WHERE 信息，不应出现在 skill 定义中。

## 决策

### 1. SKILL.md 仅保留 name + description

```yaml
---
name: paperutils
description: Query papers, DOIs, PMIDs, datasets
---
# Skill body...
```

移除 `path` 和 `source` 字段。SKILL.md 的职责是描述技能是什么、怎么用，不关心从哪来。

### 2. 职责边界

```
Agent 声明（agent.md）:
  requires.skills: [paperutils]    ← 我需要什么

环境声明（pixi.toml 或 environment.yml）:
  [npm-dependencies]               ← 从哪安装
  "@scope/paperutils-skill" = "^1.0"

  [tasks]
  install-skills = "skit install paperutils"
```

### 3. loopflow 不约束 skill 管理器

loopflow 不强制使用 skit、skill.sh、npm 或任何特定工具。Workflow 作者在环境文件中自由选择。

### 4. loopflow 的 prompt 注入仍然生效

当 workflow 没有声明 `meta.requires.environment` 时，loopflow 的 prompt 注入作为 fallback：查找 `~/.agents/skills/` → `~/.loopflow/skills/`，注入名称+描述+路径。这是"无环境文件时的默认行为"，不是"skill 管理策略"。

### 5. Skill 存储隔离

与 conda 环境隔离同模式：每个 workflow 的 skill 存储到项目本地 `.skills/` 目录，不污染全局。

```toml
# pixi.toml
[activation.env]
SKILLS_HOME = "${PIXI_PROJECT_ROOT}/.skills"
```

```
bio-reproducer/
├── workflow.py
├── agents/
├── pixi.toml
├── .pixi/              ← pixi env（瞬态，可重建）
└── .skills/            ← project skills（持久，随项目）
```

- `.skills/` 是隐藏目录，表示自动管理，不手改
- 不与 `agents/`（手写）混淆
- `PIXI_PROJECT_ROOT` 而非 `CONDA_PREFIX`：技能属于项目，不属于环境。env 重建时 skill 不丢失

| 管理器 | 隔离方式 |
|--------|---------|
| skit | `SKILLS_HOME=.skills` 覆盖默认路径 |
| skill.sh (npm) | `npm install` 默认到 `node_modules/`，项目级 |
| 手动 | `SKILLS_HOME` 指向 `.skills/` |

隔离是环境管理器的职责，loopflow 不参与。loopflow 的保证：声明了环境文件 → 隔离由环境文件保证；未声明 → 不保证。

## 影响

- ADR 0015：SKILL.md 格式从 4 字段（name, description, path, source）简化为 2 字段（name, description）
- Spec：移除 `path`/`source` 字段说明
- 实现：`skills.py` 的 `parse_skill()` 继续只解析 name + description（无变化）
- `build_skill_prompt()` 继续工作（fallback 路径）

## 修订记录

ADR 0015 的 SKILL.md 格式由此修订：`path` 和 `source` 字段移除。