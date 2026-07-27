---
title: Plan — Schema 兜底校验 + Retry Hint 携带详细错误信息
description: 框架层类型兜底（string→number 等可兼容转换自动接受）+ json.loads 成功后补 schema 校验 + retry hint 汇总所有错误原因（BL-031）
type: plan
status: pending
created: 2026-07-27T12:30:00Z
---

# Plan: Schema 兜底校验 + Retry Hint 详细错误

## 目标

三个问题叠加：

1. **`json.loads` 成功后跳过 schema 校验**：`runner.py:446-451` 在 `json.loads` 成功后直接返回，不校验 schema。agent 返回 `{"score": "95"}`（schema 要求 number）会被静默接受。
2. **框架不做类型兜底**：agent 返回 `"95"`（string）而 schema 要求 number，框架应尽量兼容转换而非直接拒绝。
3. **retry hint 无具体错误信息**：当前 hint 只说"not valid JSON"，agent 不知道是 JSON 语法错误还是 schema 类型不匹配，每次只改格式不改结构。

修复方向：
- `json.loads` 成功后补 schema 校验
- 校验失败时先尝试类型兜底（string→number/bool、number→string 等可兼容转换）
- 兜底失败后 retry hint 汇总所有检测到的错误（字段路径、期望类型、实际值、兜底尝试结果）

## 步骤

1. **`domain/marshalling.py` — 新增 `coerce_json()` 类型兜底函数**

   ```python
   def coerce_json(obj: dict, schema: dict) -> tuple[dict | None, list[str]]:
       """尝试将 obj 中的值做兼容类型转换以满足 schema。

       返回 (coerced_obj | None, errors)。errors 记录所有尝试过的转换
       （即使成功也记录，供 retry hint 汇总）。
       """
   ```

   兜底规则（仅做安全兼容转换，不做语义猜测）：

   | Schema 期望 | 实际值 | 兜底动作 | 示例 |
  -------------|--------|---------|------|
   | `number`/`integer` | string 可 parse | `float(s)` / `int(s)` | `"95"` → `95` |
   | `boolean` | string `"true"`/`"false"` | `True` / `False` | `"true"` → `True` |
   | `string` | number/bool | `str(v)` | `95` → `"95"` |
   | `array` of T | 单个非 array 值 | `[v]`（仅当 schema min_items=1） | `"a"` → `["a"]` |
   | `enum` | string 大小写不同 | 匹配 enum 值 | `"pass"` → `"PASS"` |

   **不做**的转换：类型完全不同且无兼容路径（如 object → string）、值超出范围、结构不匹配（缺 required 字段、多余字段不裁剪）。

2. **`domain/marshalling.py` — `extract_json()`/`validate_json()` 返回错误详情**

   - `validate_json(obj, schema)` 返回 `(bool, str | None)` — 失败时携带 `jsonschema.ValidationError` 的 `absolute_path` + `expected` + `found`。
   - `extract_json(text, schema)` 返回 `(dict | None, str | None)` — 失败时携带校验错误信息。

3. **`application/runner.py:446-451` — `json.loads` 成功后补 schema 校验 + 兜底**

   ```python
   try:
       result = json.loads(text)
       # 1. 先校验 schema
       valid, val_error = validate_json(result, schema)
       if not valid:
           # 2. 校验失败 → 尝试兜底
           coerced, coercion_errors = coerce_json(result, schema)
           if coerced is not None:
               # 兜底成功 → 接受
               result = coerced
           else:
               # 兜底也失败 → 记录所有错误，走 retry
               last_errors = [val_error] + coercion_errors
               if attempt >= max_retries:
                   raise AgentError(
                       f"Schema validation failed after {max_retries} retries. "
                       f"Last errors: {'; '.join(last_errors)}"
                   )
               continue  # retry with aggregated hint
       self._write_cache(...)
       return result, backend_sid
   except json.JSONDecodeError:
       extracted, extract_error = extract_json(text, schema)
       if extracted is not None:
           # extract_json 内部已做 validate_json，extracted 是通过校验的
           self._write_cache(...)
           return extracted, backend_sid
       # extract 也失败 → 走 retry
       last_errors = [extract_error or "JSON extraction failed"]
       if attempt >= max_retries:
           raise AgentError(f"... {last_errors[-1]}")
       continue
   ```

4. **`application/runner.py:396-406` — retry hint 汇总所有错误**

   retry hint 从 `last_errors` 列表构建（而非单一字符串）：

   ```
   Your previous response did not pass schema validation.
   Errors detected:
   - Field 'score': expected number, got string "95" (coercion attempted: succeeded)
   - Field 'verdict': expected enum [REPRODUCED, PARTIAL, FAILED, BLOCKED], got "pass" (coercion attempted: case mismatch, failed)
   Please fix the above fields and respond with a JSON object matching the schema.
   ```

   当 `json.loads` 失败时（JSON 语法错误），hint 保持通用"not valid JSON"措辞。

5. **`application/execution.py:121` — error_summary 携带具体原因**

   `AgentError` 消息中附带最后一次的错误列表，使 `error_summary` 包含具体原因。

6. **测试**

   - 单元测试：`coerce_json` 各转换规则（string→number、string→bool、number→string、enum case、array wrap）
   - 单元测试：`coerce_json` 不做的转换（object→string、缺 required 字段）
   - 单元测试：mock agent 返回纯 JSON `{"score":"95"}`（schema 要求 number），验证兜底成功，不触发 retry
   - 单元测试：mock agent 返回 `{"verdict":"pass"}`（schema enum 要求大写），验证兜底成功
   - 单元测试：mock agent 返回 `{"score":"abc"}`（非数字字符串），验证兜底失败，retry hint 包含字段路径和兜底失败原因
   - 单元测试：mock agent 返回非纯 JSON（文字包裹），`extract_json` 提取后 schema 校验，retry hint 包含详情
   - 单元测试：mock agent 返回非法 JSON，retry hint 保持通用措辞
   - 集成测试：agent 连续返回 schema 不匹配的 JSON，验证最终 AgentError 消息包含错误列表
   - 适配 `tests/unit/test_runtime.py` 中 `extract_json`（约 11 处）和 `validate_json`（约 2 处）调用

## AC 覆盖

- AC-026-N-4（新增）：schema 校验失败时 retry hint 包含具体字段路径
- AC-026-N-5（新增）：string "95" → number 95 兜底成功，不触发 retry
- AC-026-E-2（新增）：retry 耗尽后 AgentError 消息包含最后一次校验错误

## Constraints

- 不改 `extract_json` 的 brace-matching 扫描逻辑（ADR-0024 不变）
- 不改 retry 次数和退避策略（ADR-0011/0044 不变）
- 兜底只做安全兼容转换，不做语义猜测（如不猜 `"yes"` → `True`，只认 `"true"`/`"false"`）
- retry hint 长度不超过 500 字符（截断长错误列表）
- `validate_json`/`extract_json` 返回值变更需更新所有调用方
- 兜底转换后的值必须通过 `validate_json` 二次校验才接受

## Checkpoint

- `domain/marshalling.py`：新增 `coerce_json()`；`extract_json`/`validate_json` 返回值变更
- `application/runner.py`：schema 校验 + 兜底流程；retry hint 从错误列表构建
- `application/execution.py`：AgentError 消息丰富
- 测试全绿（含新 `coerce_json` 单元测试）

## 风险

- `extract_json`/`validate_json` 返回值 breaking change。受影响调用方：`runner.py:453`（1 处）、`tests/unit/test_runtime.py`（`extract_json` 约 11 处、`validate_json` 约 2 处）。
- **行为变更**：之前静默接受的类型不匹配 JSON 现在（兜底失败后）会触发 retry。需确认无 workflow 依赖此"宽松"行为。兜底能覆盖大部分常见场景（string→number 等），降低行为变更影响。
- 兜底可能引入误转换：如 agent 真意返回字符串 `"95"` 但 schema 要求 number，兜底后变成 `95`。这是合理的——schema 是契约，类型以 schema 为准。
- `jsonschema.ValidationError` 的 message 可能过长。需截断。

## 调查记录

- **frontmatter 移除（ADR-0051）与 schema 可见性的关系**：`output` schema 在 `runner.py:243-251` 独立注入，与 frontmatter 无关，**无回归**。`input` schema 在 ADR-0051 后不再出现在 prompt body 中，但这是 ADR-0051 的设计意图（frontmatter 是元数据）。schema 频繁出错的根因是框架不做兜底 + json.loads 成功后跳过校验，与 frontmatter 移除无关。
