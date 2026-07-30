"""Hotfix 0.27.1: `loopflow web` must serve the WebUI without a manual sync step.

Regression for the 0.27.0 release defect: the installed/develop wheel had no
static assets, so GET / returned 404 file_not_found.
"""
from __future__ import annotations

import http.client
import threading
import time

import pytest

from loopflow.presentation.web.server import create_server


def _free_server() -> tuple:
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


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
