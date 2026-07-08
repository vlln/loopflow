<!-- 编码规范。项目自定义。Agent 在 DEVELOP 阶段读取。 -->

---

## 一、开发环境

Python 3.10+，零外部依赖（仅标准库）。

```bash
# 无需安装依赖，直接可运行
python3 -m pytest tests/ -v
```

**构建/配置入口：**

| 文件 | 用途 |
|------|------|
| `src/loopflow/` | 主程序入口 |
| `tests/` | 测试目录 |

---

## 二、代码风格

- 格式化：遵循 PEP 8
- 命名：
  - 文件：snake_case（Python 模块）
  - 变量/函数：snake_case
  - 类/接口：PascalCase
  - 常量：UPPER_SNAKE_CASE

---

## 三、Commit 规则

### 格式

```
<type>(<scope>): <简短描述>
```

| type | 说明 |
|------|------|
| feat | 新功能 |
| fix | Bug 修复 |
| docs | 文档变更（必须独立提交，不与代码混合） |
| refactor | 重构 |
| test | 测试相关 |
| chore | 构建/工具/依赖 |

### devloop 约定

- 文档变更和代码变更永远分开 commit
- 阶段推进伴随独立 commit，前缀 `docs(state):`
- 文档 commit 格式：`docs(<scope>): <简述>`

---

## 四、分支策略

遵循 Gitflow：

```
main     ─────●──────────●────→  (tag: v1.0, v1.1)
              ↑          ↑
release  ──── v1.0 ───── v1.1
              ↑          ↑
develop  ────●──●──●──●──●──→  (持续集成)
              ↑  ↑  ↑
             ci/ feat/ fix/
```

| 分支 | 用途 | 从哪拉 | 合并到哪 |
|------|------|--------|---------|
| `main` | 仅含 release 节点，始终可部署 | — | — |
| `develop` | 持续集成分支 | `main` | — |
| `feat/*` `refactor/*` `perf/*` | 功能开发 | `develop` | `develop` |
| `ci/*` `test/*` `build/*` | 基建搭建 | `develop` | `develop` |
| `fix/*` | 集成修复 | `develop` | `develop` |
| `spike/*` | ADR 技术验证 | `develop` | 不合并（保留） |
| `release/*` | 版本发布 | `develop` | `main` + `develop` |
| `hotfix/*` | 生产热修复 | `main` | `main` + `develop` |

一个执行容器 = 一个分支，编号与执行容器对应。分支类型与 commit type 一致。

Merge 策略：squash merge（保持 develop 历史线性）。

---

## 五、测试

### 测试命令

<!-- 根据项目实际配置 -->

| 命令 | 用途 |
|------|------|
| `uv run pytest tests/unit/ -v` | 单元测试 |
| `uv run pytest tests/integration/ -v` | 集成测试 |
| `uv run pytest tests/ -v --cov=src/loopflow --cov-fail-under=80` | 全部测试 + 覆盖率 |

### 测试目录

| 层级 | 目录路径 | 说明 |
|------|---------|------|
| 单元测试 | `tests/unit/` | 纯函数/类测试，无外部依赖 |
| 集成测试 | `tests/integration/` | 模块间协作，需 mock backend |

---

## 六、PR 流程

<!-- PR 描述模板、Review 要求、合并策略 -->

---

## 七、行为准则

<!-- 项目行为准则，可引用 Contributor Covenant -->

---

## 八、许可证

MIT
