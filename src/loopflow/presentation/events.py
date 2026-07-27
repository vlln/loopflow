"""Presentation events — log output (presentation layer)."""

from __future__ import annotations

from loopflow.infrastructure.context import _emit_log, _write_event

# Mutable state accessed via module attribute
import loopflow.infrastructure.context as _ctx_module
