"""Presentation events — phase output (presentation layer)."""

from __future__ import annotations

import time

from loopflow.infrastructure.context import _emit_log, _write_event

# Mutable state accessed via module attribute
import loopflow.infrastructure.context as _ctx_module


def _emit_phase(title: str) -> None:
    _ctx = _ctx_module._ctx
    prev_phase = _ctx._current_phase
    _ctx._current_phase = title

    # --from-phase: check if we've reached the target
    if _ctx.from_phase and title == _ctx.from_phase:
        _ctx._reached_from_phase = True

    # --only-phase: check if we've passed the target
    if _ctx.only_phase and prev_phase == _ctx.only_phase:
        _ctx._past_only_phase = True

    if _ctx.live is not None:
        _ctx.live.console.log(f"[loopflow] Phase: {title}")
    else:
        import sys
        print(f"[loopflow] Phase: {title}", file=sys.stderr, flush=True)

    _write_event({"type": "phase", "title": title, "ts": time.time()})

    if _ctx.graph is not None:
        _ctx.graph.record(_ctx._prev_phase, title)
        _ctx._prev_phase = title
        if _ctx.live is not None:
            from loopflow.presentation.display.graph_renderer import TerminalGraphRenderer
            renderer = TerminalGraphRenderer(_ctx.graph)
            _ctx.live.update(renderer.render())