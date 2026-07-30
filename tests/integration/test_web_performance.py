"""SYSTEM_TEST performance special: Runs first-paint p95 < 500ms (Spec §7 NFR).

Fixture: 1000 Runs (each run.json ~2KB) + selected Run with 1000 1KB events,
server warm with OS file cache. Measures 30 reads of the first-paint APIs.
"""
from __future__ import annotations

import threading
import time

import pytest

from loopflow.application.web import WebApplication
from loopflow.infrastructure.web_resources import BackendRepository, LoopRepository, QueueRepository
from loopflow.infrastructure.web_storage import RunRepository
from loopflow.presentation.web.server import create_server
from tests.web_support.factories import WebFixtureFactory
from tests.web_support.http import JsonHttpClient


class _Probe:
    def identity(self, pid):
        return "same" if pid == 7 else None

    def group_id(self, pid):
        return 70 if pid == 7 else None

    def terminate(self, pid):
        return pid == 7

    def terminate_group(self, pgid, *, grace_seconds=0.2):
        return "terminated"


class _Backend(BackendRepository):
    def list(self):
        return []

    def diagnose(self, name, timeout_ms):
        return {}


class _Executor:
    def start(self, loop, args, options, run_id=None, working_directory=None):
        return "x"


@pytest.fixture
def perf_api(tmp_path):
    factory = WebFixtureFactory(tmp_path)
    factory.create_loop("hello")
    runs = RunRepository(factory.runs, _Probe())
    app = WebApplication(runs, LoopRepository(factory.loops, runs), QueueRepository(tmp_path / "queue"), _Backend(), _Executor(), {"kimi"})
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html>")
    (static / "assets" / "app.js").write_text("x")
    server = create_server("127.0.0.1", 0, application=app, static_root=static)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield JsonHttpClient("127.0.0.1", server.server_port), factory
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, int(0.95 * len(ordered)))
    return ordered[index]


def test_runs_first_paint_p95_under_500ms(perf_api):
    client, factory = perf_api
    selected = factory.create_performance_runs(count=1000, event_count=1000)

    # warm the OS file cache / server read path before measuring
    client.request("GET", "/api/v1/runs?limit=50")
    client.request("GET", f"/api/v1/runs/{selected.name}")

    list_samples: list[float] = []
    detail_samples: list[float] = []
    for _ in range(30):
        start = time.perf_counter()
        response = client.request("GET", "/api/v1/runs?limit=50")
        list_samples.append(time.perf_counter() - start)
        assert response.status == 200

        start = time.perf_counter()
        detail = client.request("GET", f"/api/v1/runs/{selected.name}")
        detail_samples.append(time.perf_counter() - start)
        assert detail.status == 200
        assert detail.json()["agent_graph"] is not None

    list_p95 = _p95(list_samples)
    detail_p95 = _p95(detail_samples)
    assert list_p95 < 0.5, f"runs list p95 {list_p95*1000:.0f}ms >= 500ms"
    assert detail_p95 < 0.5, f"run detail p95 {detail_p95*1000:.0f}ms >= 500ms"
