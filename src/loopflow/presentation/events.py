"""Presentation events — log and phase output (presentation layer)."""

from __future__ import annotations

import sys
import time

from loopflow.infrastructure.context import _write_event


def _emit_phase(title: str) -> None:
    import loopflow.infrastructure.context as _ctx_module
    _ctx = _ctx_module._ctx
    _ctx._current_phase = title

    if _ctx.live is not None:
        _ctx.live.console.log(f"[loopflow] Phase: {title}")
    else:
        print(f"[loopflow] Phase: {title}", file=sys.stderr, flush=True)

    _write_event({"type": "phase", "title": title, "ts": time.time()})

    if _ctx.graph is not None:
        _ctx.graph.record(_ctx._prev_phase, title)
        _ctx._prev_phase = title
        if _ctx.live is not None:
            from loopflow.presentation.display.graph_renderer import TerminalGraphRenderer
            renderer = TerminalGraphRenderer(_ctx.graph)
            _ctx.live.update(renderer.render())


def _emit_log(message: str) -> None:
    import loopflow.infrastructure.context as _ctx_module
    _ctx = _ctx_module._ctx

    if _ctx.live is not None:
        _ctx.live.console.log(f"[loopflow] {message}")
    else:
        print(f"[loopflow] {message}", file=sys.stderr, flush=True)

    _write_event({"type": "log", "message": message, "ts": time.time()})