# 0091 — 框架健壮性修复（BL-017/018/019）

对应阶段：`DEVELOP`（0.23.0 迭代，服务 ADR-0051）。

| 单元 | Plan | Report | 状态 |
|------|------|--------|------|
| 01 | [框架健壮性修复](01-plan-framework-robustness.md) | [Report](01-report-framework-robustness.md) | done |

## 范围

- BL-017：`render_template` 的 `_replace` 返回 `str(value)`，防止 integer/None 模板变量触发 `re.sub` TypeError
- BL-018：`parse_agent` 取 `parts[2].strip()` 为 body，排除 frontmatter，避免 prompt 以 `---` 开头被 CLI 后端（pi）误解析为未知选项（ADR-0051）
- BL-019：pi 后端 `_parse_line` 改用 `text_end` 消息级事件，弃 `text_delta` token 级片段，修复 `_extract_text` 的 `"\n".join` 破坏流式 JSON
- chore：uv.lock 版本同步至 0.22.0

## 非范围

- 不改 deep-research loop 代码（`loop-library/loops/deep-research`）：bug 在框架层，loop 只是暴露器
- 不重构 work_dir 传递链（见 [0092](../0092-work-dir/README.md)）

## 依据

- ADR-0051（parse_agent body 切分）
- BL-017/018/019（backlog）
