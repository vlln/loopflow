"""Workflow runtime — public API: agent, parallel, pipeline, phase, log, workflow.

All infrastructure (context, backends, worktree) and presentation (events)
are in their respective layers. This module is the application orchestrator.
"""

from __future__ import annotations

import importlib.util
import json
import threading
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
from loopflow.infrastructure.backends import manager as _backend_manager
from loopflow.infrastructure.worktree import _create_worktree
from loopflow.presentation.events import _emit_log, _emit_phase
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

    # --from-phase: skip agent calls before the target phase
    if ctx.from_phase and not ctx._reached_from_phase:
        return AgentResult(status="complete", turns=0, reason="skipped")

    # --only-phase: stop after the target phase completed
    if ctx.only_phase and ctx._past_only_phase:
        return AgentResult(status="blocked", turns=0, reason="stopped-after-phase")

    ad = None
    if ctx.loop_dir is not None and agent_def is not None:
        agent_path = ctx.loop_dir / "agents" / f"{agent_def}.md"
        if agent_path.is_file():
            try:
                ad = parse_agent(agent_path)
            except (ValueError, FileNotFoundError):
                ad = None

    backend_instance = None if _backend_manager._mock_mode else _make_backend(backend)
    try:
        def _invoke(prompt_str, session_name, **kw):
            return _run_subagent(
                prompt_str, session_name, backend=backend,
                model=kw.get("model"), cwd=kw.get("cwd"),
                agent_def=kw.get("agent_def"),
                cache_path=kw.get("cache_path"),
                resume_session_id=kw.get("resume_session_id"),
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
        )
        result = runner.run(
                prompt,
                goal=goal,
                model=model,
                schema=schema,
                isolation=isolation,
                max_retries=max_retries,
                goal_max_iterations=goal_max_iterations,
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

    def _run(idx: int, fn: Callable[[], Any]) -> None:
        try:
            results[idx] = fn()
        except Exception:
            results[idx] = None

    threads: list[threading.Thread] = []
    for i, fn in enumerate(thunks):
        t = threading.Thread(target=_run, args=(i, fn), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return results


def pipeline(items: list[Any], *stages: Callable) -> list[Any]:
    results: list[Any] = [None] * len(items)

    def _process(idx: int, item: Any) -> None:
        result: Any = item
        for stage in stages:
            try:
                if stage is stages[0]:
                    result = stage(item, idx)
                else:
                    result = stage(result, item, idx)
            except Exception:
                result = None
                break
            if result is None:
                break
        results[idx] = result

    threads: list[threading.Thread] = []
    for i, item in enumerate(items):
        t = threading.Thread(target=_process, args=(i, item), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
    return results


def workflow(script_path: str, args: dict | None = None) -> Any:
    """Run another workflow script as a sub-workflow (one level deep)."""
    path = Path(script_path)
    if not path.is_file():
        return None

    spec = importlib.util.spec_from_file_location(
        f"wf_sub_{_ctx_module._ctx.run_id}_{path.stem}", path)
    if spec is None or spec.loader is None:
        return None

    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception:
        return None

    if not hasattr(mod, "run"):
        return None

    import inspect
    sig = inspect.signature(mod.run)
    run_kwargs = dict(
        agent=agent, parallel=parallel, pipeline=pipeline,
        phase=phase, log=log, args=args or {},
        workflow=workflow,
    )
    if "state" in sig.parameters:
        run_kwargs["state"] = _ctx_module._ctx.state
    return mod.run(**run_kwargs)


def phase(title: str) -> None:
    _emit_phase(title)


def log(message: str) -> None:
    _emit_log(message)