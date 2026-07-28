"""Workflow runtime — public API: agent, parallel, pipeline, log, workflow.

All infrastructure (context, backends, worktree) and presentation (events)
are in their respective layers. This module is the application orchestrator.
"""

from __future__ import annotations

import importlib.util
import json
import threading
import types
from pathlib import Path
from typing import Any, Callable

from loopflow.infrastructure.context import (
    RunContext,
    State,
    _persist_state,
    _write_cache,
    _write_event,
    set_context,
)
from loopflow.infrastructure.intervention import InterventionIdentity, request_or_answer
from loopflow.infrastructure.backends import manager as _backend_manager
from loopflow.infrastructure.worktree import _create_worktree
from loopflow.presentation.events import _emit_log
from loopflow.domain.goal_loop import AgentResult

# Mutable state accessed via module attribute (not import-time binding)
import loopflow.infrastructure.context as _ctx_module

# Re-export for backward compatibility
set_mock = _backend_manager.set_mock
_make_backend = _backend_manager._make_backend
_run_subagent = _backend_manager._run_subagent
_run_mock = _backend_manager._run_mock
_run_mock_auto = _backend_manager._run_mock_auto
_mock_mode = _backend_manager._mock_mode


# ── public API ───────────────────────────────────────────────────────────

def agent(
    prompt: str,
    *,
    schema: dict | None = None,
    max_retries: int = 3,
    isolation: str | None = None,
    label: str | None = None,
    backend: str | None = None,
    model: str | None = None,
    agent_def: str | None = None,
    goal: str | None = None,
    goal_max_iterations: int = 10,
    **kwargs: str,
) -> Any:
    """Run an agent call. Thin facade over AgentRunner."""
    from loopflow.infrastructure.repository import parse_agent
    from loopflow.application.runner import AgentRunner

    ctx = _ctx_module._ctx
    backend = backend or getattr(ctx, "default_backend", None)
    model = model or getattr(ctx, "default_model", None)

    # ADR-0049: read transport/backend from execution_options (CLI --transport / --backend)
    exec_opts = getattr(ctx, "execution_options", {}) or {}
    transport = exec_opts.get("transport") or kwargs.pop("transport", None)
    if backend is None:
        backend = exec_opts.get("backend")

    ad = None
    if ctx.loop_dir is not None and agent_def is not None:
        agent_path = ctx.loop_dir / "agents" / f"{agent_def}.md"
        if agent_path.is_file():
            try:
                ad = parse_agent(agent_path)
            except (ValueError, FileNotFoundError):
                ad = None

    backend_instance = None if _backend_manager._mock_mode else _make_backend(backend, transport=transport)
    try:
        def _invoke(prompt_str, session_name, **kw):
            return _run_subagent(
                prompt_str, session_name, backend=backend,
                model=kw.get("model"), cwd=kw.get("cwd"),
                agent_def=kw.get("agent_def"),
                cache_path=kw.get("cache_path"),
                resume_session_id=kw.get("resume_session_id"),
                call_id=kw.get("call_id"),
            )

        runner = AgentRunner(
            ad, backend_instance, ctx,
            invoke_fn=_invoke,
            log_fn=_emit_log,
            write_event_fn=_write_event,
            write_cache_fn=_write_cache,
            persist_state_fn=_persist_state,
            create_worktree_fn=_create_worktree,
            mock_mode=_backend_manager._mock_mode,
            mock_fn=_run_mock,
            mock_auto_fn=_run_mock_auto,
            backend_name=backend,
        )
        result = runner.run(
                prompt,
                goal=goal,
                model=model,
                schema=schema,
                isolation=isolation,
                max_retries=max_retries,
                goal_max_iterations=goal_max_iterations,
                label=label,
                agent_def=agent_def,
                **kwargs,
            )
        if result.status != "complete":
            _emit_log(f"Agent blocked: {result.reason}")
        return result
    finally:
        if backend_instance:
            backend_instance.close()


def parallel(thunks: list[Callable[[], Any]]) -> list[Any]:
    results: list[Any] = [None] * len(thunks)
    errors: list[BaseException | None] = [None] * len(thunks)
    ctx = _ctx_module._ctx
    namespaces = ctx.reserve_parallel(len(thunks))

    # Record fork in agent graph and emit fork event
    current_call_id = getattr(ctx, '_current_call_id', None)
    _write_event({"type": "fork_start", "call_id": current_call_id, "count": len(thunks)})

    def _run(idx: int, fn: Callable[[], Any]) -> None:
        ctx.enter_call_namespace(namespaces[idx])
        try:
            results[idx] = fn()
        except Exception as error:
            errors[idx] = error
            results[idx] = None
        finally:
            ctx.leave_call_namespace()

    threads: list[threading.Thread] = []
    for i, fn in enumerate(thunks):
        t = threading.Thread(target=_run, args=(i, fn), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    # Record join in agent graph and emit fork_end event
    _write_event({"type": "fork_end", "call_id": current_call_id})

    if ctx.resume:
        first = next((error for error in errors if error is not None), None)
        if first is not None:
            raise first
    return results


def pipeline(items: list[Any], *stages: Callable) -> list[Any]:
    results: list[Any] = [None] * len(items)
    errors: list[BaseException | None] = [None] * len(items)
    ctx = _ctx_module._ctx
    namespaces = ctx.reserve_parallel(len(items))

    def _process(idx: int, item: Any) -> None:
        ctx.enter_call_namespace(namespaces[idx])
        result: Any = item
        try:
            for stage in stages:
                if stage is stages[0]:
                    result = stage(item, idx)
                else:
                    result = stage(result, item, idx)
                if result is None:
                    break
        except Exception as error:
            errors[idx] = error
            result = None
        finally:
            ctx.leave_call_namespace()
        results[idx] = result

    threads: list[threading.Thread] = []
    for i, item in enumerate(items):
        t = threading.Thread(target=_process, args=(i, item), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    if ctx.resume:
        first = next((error for error in errors if error is not None), None)
        if first is not None:
            raise first
    return results


def workflow(script_path: str, args: dict | None = None) -> Any:
    """Run another workflow script as a sub-workflow (one level deep)."""
    path = Path(script_path)
    if not path.is_file():
        return None

    mod = types.ModuleType(f"wf_sub_{_ctx_module._ctx.run_id}_{path.stem}")
    mod.__file__ = str(path)
    try:
        source = path.read_text(encoding="utf-8")
        exec(compile(source, str(path), "exec"), mod.__dict__)
    except Exception:
        return None

    if not hasattr(mod, "run"):
        return None

    from loopflow.infrastructure.workflow_args import accepted_kwargs
    run_kwargs = dict(
        agent=agent, parallel=parallel, pipeline=pipeline,
        log=log, args=args or {}, intervene=intervene,
        workflow=workflow,
    )
    run_kwargs["state"] = _ctx_module._ctx.state
    return mod.run(**accepted_kwargs(mod.run, run_kwargs))


def log(message: str) -> None:
    _emit_log(message)


def intervene(
    key: str,
    prompt: str,
    schema: dict | None = None,
    *,
    options: list[str] | tuple[str, ...] | None = None,
    allow_custom: bool = True,
    default: Any = None,
    timeout: float | None = None,
) -> Any:
    if not isinstance(key, str) or not key:
        raise ValueError("intervention key must be a non-empty string")
    if not isinstance(prompt, str) or not prompt:
        raise ValueError("intervention prompt must be a non-empty string")
    if schema is not None and not isinstance(schema, dict):
        raise ValueError("intervention schema must be object or null")
    if options is None:
        request_options: tuple[str, ...] = ()
    elif isinstance(options, (list, tuple)) and all(isinstance(item, str) for item in options):
        request_options = tuple(options)
    else:
        raise ValueError("intervention options must be a string array")
    if not isinstance(allow_custom, bool):
        raise ValueError("intervention allow_custom must be boolean")
    # ADR-0056 §3: a timeout only makes sense with a fallback default, and the
    # default must pass the same validation answer_requests() would apply
    if timeout is not None:
        if default is None:
            raise ValueError("intervention timeout requires a default")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError("intervention timeout must be a positive number of seconds")
    if default is not None:
        from loopflow.infrastructure.intervention import InterventionValidationError, validate_response
        try:
            validate_response(
                {"options": list(request_options), "allow_custom": allow_custom, "schema": schema},
                default,
            )
        except InterventionValidationError as error:
            raise ValueError(f"intervention default is invalid: {error}") from error
    ctx = _ctx_module._ctx
    return request_or_answer(
        ctx.run_dir,
        ctx.run_id,
        InterventionIdentity(
            key=key,
            prompt=prompt,
            options=request_options,
            allow_custom=allow_custom,
            schema=schema,
            resume_mode="replay",
            default=default,
            timeout_seconds=timeout,
        ),
        unattended=bool(ctx.execution_options.get("unattended")),
    )
