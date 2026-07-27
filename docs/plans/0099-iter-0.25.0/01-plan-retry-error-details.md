---
title: Plan — Retry Hint 携带具体 Schema 校验错误信息
description: 当 agent 返回的 JSON 通过 json.loads 但 schema 校验失败时，retry hint 应包含具体字段路径和期望类型，而非通用"not valid JSON"（BL-031）
type: plan
status: pending
created: 2026-07-27T12:30:00Z
---

# Plan: Retry Hint 携带具体 Schema 校验错误信息

## 目标

当 agent 返回的 JSON 语法正确但 schema 校验失败时（如 `decisions` 字段应为对象数组但返回了字符串数组），retry hint 当前只说"Your previous response was not valid JSON"——agent 以为是 JSON 语法错误，每次只改格式不改结构，直到耗尽重试次数。

修复方向：在 retry hint 中区分两种失败模式（JSON 语法错误 vs schema 校验错误），schema 校验失败时附带 `jsonschema.ValidationError` 的具体信息（字段路径、期望类型、实际值）。

## 步骤

1. **`domain/marshalling.py` — `extract_json()`/`validate_json()` 返回错误详情**

   当前 `extract_json()` 返回 `dict | None`。改为在 schema 校验失败时，不仅返回 None，还把 `jsonschema.ValidationError` 的信息格式化为可读字符串（如 `Field 'decisions': expected array of objects, got array of strings`）。

   方案：`extract_json()` 返回 `tuple[dict | None, str | None]`——`(parsed_obj, validation_error)`。`validate_json()` 改为返回 `(bool, str | None)`，在失败时携带 ValidationError 的 `absolute_path` + `expected` + `found` 信息。

2. **`application/runner.py:446-451` — `json.loads` 成功后补 schema 校验**

   **当前缺陷**：`json.loads(text)` 成功后直接 `return result`（line 451），**不校验 schema**。agent 返回 `{"score": "95"}`（schema 要求 number 但返回 string）会被直接接受。

   修复：在 `json.loads` 成功后、返回前，调用 `validate_json(result, schema)`。若校验失败，走 retry 路径（与 `extract_json` 返回 None 时相同），retry hint 携带 schema 校验错误。

   ```python
   # runner.py:446-451 修改后
   try:
       result = json.loads(text)
       valid, val_error = validate_json(result, schema)
       if not valid:
           last_validation_error = val_error
           if attempt >= max_retries:
               raise AgentError(f"... schema validation: {val_error}")
           continue  # retry with hint
       self._write_cache(...)
       return result, backend_sid
   except json.JSONDecodeError:
       ...
   ```

3. **`application/runner.py:396-406` — retry hint 区分两种失败模式**

   当 `json.loads` 失败时（JSON 语法错误），hint 保持通用"not valid JSON"措辞。

   当 schema 校验失败时（`json.loads` 成功但 `validate_json` 返回 False，或 `extract_json` 返回 `(None, validation_error)`），hint 改为：

   ```
   Your previous response was valid JSON but did not match the required schema.
   Validation error: {validation_error}
   Please fix the above field and respond with a JSON object matching the schema.
   ```

4. **`application/execution.py:121` — error_summary 携带具体原因**

   当 `AgentError("Agent failed to return valid JSON after N retries")` 抛出时，在异常消息中附带最后一次 schema 校验错误详情，使 `error_summary` 和 `error_traceback` 包含具体原因。

5. **测试**

   - 单元测试：mock agent 返回纯 JSON `{"score":"95"}`（schema 要求 number），验证 `json.loads` 成功后 `validate_json` 拦截，retry hint 包含字段路径信息
   - 单元测试：mock agent 返回非纯 JSON（文字包裹），`extract_json` 提取后 schema 校验失败，retry hint 包含字段路径信息
   - 单元测试：mock agent 返回非法 JSON，验证 retry hint 保持通用措辞
   - 集成测试：agent 连续返回 schema 不匹配的 JSON，验证最终 AgentError 消息包含最后一次的校验错误
   - 适配 `tests/unit/test_runtime.py` 中 `extract_json` 的 11 处调用（约 lines 1030-1083）和 `validate_json` 的 2 处调用（约 lines 1086-1094），更新返回值解构

## AC 覆盖

- AC-026-N-4（新增）：schema 校验失败时 retry hint 包含具体字段路径
- AC-026-E-2（新增）：retry 耗尽后 AgentError 消息包含最后一次校验错误

## Constraints

- 不改 `extract_json` 的 brace-matching 扫描逻辑（ADR-0024 的提取策略不变）
- 不改 retry 次数和退避策略（ADR-0011/0044 的重试机制不变）
- retry hint 长度不超过 500 字符（截断长 validation error）
- `validate_json` 返回值变更需更新所有调用方

## Checkpoint

- `domain/marshalling.py`：`extract_json` 和 `validate_json` 返回值变更，所有调用方适配
- `application/runner.py`：retry hint 构建逻辑修改
- `application/execution.py`：AgentError 消息丰富
- 测试全绿

## 风险

- `extract_json` 返回值从 `dict | None` 变为 `tuple[dict | None, str | None]`，是 breaking change for internal API。受影响调用方：`application/runner.py:453`（1 处）、`tests/unit/test_runtime.py`（`extract_json` 11 处约 lines 1030-1083、`validate_json` 2 处约 lines 1086-1094）。
- **新发现缺陷**：当前 `runner.py:446-451` 在 `json.loads` 成功后直接返回，不校验 schema。agent 返回类型不匹配的纯 JSON 会被静默接受。本 Plan 步骤 2 修复此缺陷，但改变了既有行为——之前"接受"的 response 现在会触发 retry。需确认无 workflow 依赖此"宽松"行为。
- `jsonschema.ValidationError` 的 `message` 属性可能过长。需截断到合理长度（≤ 500 字符）。
