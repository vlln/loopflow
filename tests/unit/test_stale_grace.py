"""AC-029 stale 失联宽限期场景（ADR-0046 / BR-052）。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from loopflow.application.execution import execute_workflow
from loopflow.infrastructure.web_storage import STALE_GRACE_SECONDS, RunRepository
from tests.recovery_support.fixtures import RunFactory


class Probe:
    """进程探活 stub：一律探活失败，running run 判定为 stale。"""

    def identity(self, pid):
        return None

    def group_id(self, pid):
        return None

    def terminate(self, pid):
        return True

    def terminate_group(self, process_group_id, *, grace_seconds=0.2):
        return "gone"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class TestStaleGracePeriod:
    def test_ac029_n1_first_stale_detection_writes_stale_since(self, tmp_path):
        factory = RunFactory(tmp_path)
        path = factory.create("run-1", status="running")

        summary = RunRepository(tmp_path, Probe()).read_summary(tmp_path / "run-1")

        assert summary["status"] == "stale"
        metadata = json.loads(path.read_text())
        assert abs((_now() - _parse(metadata["stale_since"])).total_seconds()) < 60
        assert summary["stale_since"] == metadata["stale_since"]
        remaining = summary["stale_grace_remaining_seconds"]
        assert STALE_GRACE_SECONDS - 60 < remaining <= STALE_GRACE_SECONDS

    def test_ac029_n2_worker_terminal_write_clears_stale_since(self, tmp_path, monkeypatch):
        home = tmp_path / "home"
        loops = home / "loops"
        loop = loops / "hello"
        loop.mkdir(parents=True)
        (loop / "loop.md").write_text("---\nname: hello\n---\n", encoding="utf-8")
        (loop / "workflow.py").write_text("def run(**kwargs):\n    return None\n", encoding="utf-8")
        monkeypatch.setenv("LOOPFLOW_HOME", str(home))
        monkeypatch.setenv("LOOPFLOW_LOOPS_DIR", str(loops))
        run = tmp_path / "run"
        run.mkdir()
        previous = {
            "run_id": "same",
            "loop": "hello",
            "status": "failed",
            "args": {},
            "counter": 0,
            "created": "old",
            "stale_since": (_now() - timedelta(hours=1)).isoformat(),
        }
        (run / "run.json").write_text(json.dumps(previous), encoding="utf-8")

        execute_workflow("hello", {}, {"recover": True, "recovery_mode": "retry"}, "same", run)

        metadata = json.loads((run / "run.json").read_text())
        assert metadata["status"] == "done"
        assert "stale_since" not in metadata

    def test_ac029_e1_stale_since_is_not_refreshed(self, tmp_path):
        factory = RunFactory(tmp_path)
        path = factory.create("run-1", status="running", stale_since_offset=-3600, base=_now())
        expected = json.loads(path.read_text())["stale_since"]
        repository = RunRepository(tmp_path, Probe())

        first = repository.read_summary(tmp_path / "run-1")
        second = repository.read_summary(tmp_path / "run-1")

        assert first["status"] == second["status"] == "stale"
        assert first["stale_since"] == second["stale_since"] == expected
        assert json.loads(path.read_text())["stale_since"] == expected

    def test_ac029_e2_legacy_run_records_stale_since_on_first_detection(self, tmp_path):
        factory = RunFactory(tmp_path)
        path = factory.create("run-legacy", status="running")
        assert "stale_since" not in json.loads(path.read_text())

        summary = RunRepository(tmp_path, Probe()).read_summary(tmp_path / "run-legacy")

        assert summary["status"] == "stale"
        metadata = json.loads(path.read_text())
        assert abs((_now() - _parse(metadata["stale_since"])).total_seconds()) < 60
        assert summary["stale_since"] == metadata["stale_since"]
