"""Hotfix 0.27.1: `loopflow web` must serve the WebUI without a manual sync step.

Regression for the 0.27.0 release defect: the installed/develop wheel had no
static assets, so GET / returned 404 file_not_found.
"""
from __future__ import annotations

import http.client
import threading
import time
from pathlib import Path

import pytest

from loopflow.presentation.web.server import create_server, _resolve_static_root

# CI's python jobs don't build the frontend; the wheel job (with web/dist) and
# verify-wheel-assets.py cover the end-to-end serve. Skip serve tests when no
# dist exists so CI python jobs stay green; the resolver/allowlist logic still
# runs everywhere.
_DIST = Path(__file__).resolve().parents[2] / "web" / "dist" / "index.html"
needs_dist = pytest.mark.skipif(not _DIST.is_file(), reason="web/dist not built (wheel-smoke covers serve)")


def _free_server() -> tuple:
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


@needs_dist
def test_resolve_static_root_finds_dist_or_packaged_without_sync():
    """Resolver must locate assets without a manual sync step (the 0.27.0 defect)."""
    root = _resolve_static_root()
    assert root.joinpath("index.html").is_file()


@needs_dist
def test_web_root_serves_index_html_without_manual_sync():
    server, thread = _free_server()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        conn.request("GET", "/")
        response = conn.getresponse()
        body = response.read()
        conn.close()
        assert response.status == 200
        assert b"<!doctype html>" in body or b"loopflow" in body.lower()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_web_asset_path_is_rejected_outside_static_allowlist():
    server, thread = _free_server()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        conn.request("GET", "/etc/passwd")
        response = conn.getresponse()
        conn.close()
        assert response.status == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
