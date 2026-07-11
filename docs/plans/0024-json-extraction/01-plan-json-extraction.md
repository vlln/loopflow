---
title: JSON Extraction from Agent Responses
description: 使用 jsonschema 验证 + schema-key 匹配从 text 模式后端回复中提取 JSON，跳过 retry
type: plan
status: done
created: 2026-07-11T18:00:00Z
---

# Plan 0024: JSON Extraction

## 关联文档

- ADR: [0024-json-extraction](../adr/0024-json-extraction.md)

## 步骤

### 01 — 添加 `jsonschema` 依赖

**文件：** `pyproject.toml`

```toml
dependencies = [
    "jsonschema>=4.0",
    ...
]
```

### 02 — 实现 `_extract_json` + `_validate_json`

**文件：** `src/loopflow/agent.py`

```python
def _extract_json(text: str, schema: dict) -> dict | None:
    """Extract JSON matching schema from agent text response."""
    required_keys = set(schema.get("properties", {}).keys())
    if not required_keys:
        return None
    # Find all { ... } blocks, try each against schema
    ...
    return None

def _validate_json(obj: dict, schema: dict) -> bool:
    """Validate obj against JSON Schema using jsonschema."""
    import jsonschema
    try:
        jsonschema.validate(obj, schema)
        return True
    except jsonschema.ValidationError:
        return False
```

### 03 — 集成到 `agent()` 流程

**文件：** `src/loopflow/runtime.py`

```python
# json.loads 失败后
if schema:
    extracted = _extract_json(text, schema)
    if extracted is not None and _validate_json(extracted, schema):
        result = extracted
        _write_cache(...)
        return result
    # 提取失败 → 正常 retry
```

### 04 — 更新测试

**文件：** `tests/unit/test_runtime.py`

- 新增：text 含 JSON 但被 markdown 包裹 → 提取成功
- 新增：text 含多个 JSON 块，仅匹配 schema 的被提取
- 新增：extract 后的 JSON 类型不对 → 验证失败 → retry

## 约束

- `jsonschema` 仅用于验证，不用于生成 mock 数据
- 不影响 JSON 模式后端（claude/codex）的现有行为
- `_extract_json` 返回 None 时行为与之前完全一致（进入 retry）

## 检查点

- [ ] `jsonschema` 添加到依赖
- [ ] `_extract_json` 单元测试通过
- [ ] `_validate_json` 正确拒绝类型不匹配的 JSON
- [ ] 集成到 `agent()`，提取成功时跳过 retry
- [ ] 全部测试通过