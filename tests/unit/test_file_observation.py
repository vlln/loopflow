"""Unit tests for file change observation (ADR-0039)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from loopflow.infrastructure.file_observation import (
    FileChange,
    FileChangeObserver,
    FileObservationConfig,
    FileSnapshot,
)


class TestFileObservationConfig:
    def test_default_config_is_enabled(self):
        config = FileObservationConfig.from_meta({})
        assert config.enabled is True
        assert config.exclude == []

    def test_disabled_via_meta(self):
        config = FileObservationConfig.from_meta({"file_observation": {"enabled": False}})
        assert config.enabled is False

    def test_exclude_patterns_from_meta(self):
        config = FileObservationConfig.from_meta({
            "file_observation": {"exclude": ["*.tmp", "build/"]}
        })
        assert config.exclude == ["*.tmp", "build/"]

    def test_invalid_enabled_falls_back_to_true(self):
        config = FileObservationConfig.from_meta({"file_observation": {"enabled": "yes"}})
        assert config.enabled is True

    def test_invalid_exclude_falls_back_to_empty(self):
        config = FileObservationConfig.from_meta({"file_observation": {"exclude": "not-a-list"}})
        assert config.exclude == []

    def test_default_excludes_git_and_pycache(self):
        config = FileObservationConfig()
        assert config.is_excluded(".git/config")
        assert config.is_excluded("__pycache__/module.cpython-310.pyc")
        assert config.is_excluded("app.pyc")

    def test_custom_exclude_pattern(self):
        config = FileObservationConfig.from_meta({
            "file_observation": {"exclude": ["*.log", "secrets/"]}
        })
        assert config.is_excluded("app.log")
        assert config.is_excluded("secrets/key.pem")
        assert not config.is_excluded("src/main.py")


class TestFileChangeObserver:
    def test_first_observe_marks_all_files_as_created(self, tmp_path):
        working = tmp_path / "work"
        working.mkdir()
        (working / "a.txt").write_text("hello")
        (working / "b.txt").write_text("world")
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        observer = FileChangeObserver(run_dir, working, FileObservationConfig())
        record = observer.observe("采集", "phase-1")

        assert record is not None
        assert record["seq"] == 1
        assert record["phase"] == "采集"
        assert record["phase_id"] == "phase-1"
        actions = {c["path"]: c["action"] for c in record["changes"]}
        assert actions == {"a.txt": "created", "b.txt": "created"}

    def test_second_observe_detects_modified_and_created(self, tmp_path):
        working = tmp_path / "work"
        working.mkdir()
        (working / "a.txt").write_text("hello")
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        observer = FileChangeObserver(run_dir, working, FileObservationConfig())
        observer.observe("采集", "phase-1")
        # Modify a.txt, create c.txt
        (working / "a.txt").write_text("hello world")
        (working / "c.txt").write_text("new")
        record = observer.observe("处理", "phase-2")

        assert record is not None
        assert record["seq"] == 2
        changes = {c["path"]: c for c in record["changes"]}
        assert changes["a.txt"]["action"] == "modified"
        assert changes["a.txt"]["size"] == 11
        assert changes["a.txt"]["prev_size"] == 5
        assert changes["c.txt"]["action"] == "created"

    def test_deleted_file_detected(self, tmp_path):
        working = tmp_path / "work"
        working.mkdir()
        (working / "a.txt").write_text("hello")
        (working / "b.txt").write_text("world")
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        observer = FileChangeObserver(run_dir, working, FileObservationConfig())
        observer.observe("采集", "phase-1")
        (working / "b.txt").unlink()
        record = observer.observe("处理", "phase-2")

        assert record is not None
        changes = {c["path"]: c for c in record["changes"]}
        assert changes["b.txt"]["action"] == "deleted"
        assert changes["b.txt"]["prev_size"] == 5
        assert "size" not in changes["b.txt"]

    def test_no_changes_returns_none(self, tmp_path):
        working = tmp_path / "work"
        working.mkdir()
        (working / "a.txt").write_text("hello")
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        observer = FileChangeObserver(run_dir, working, FileObservationConfig())
        observer.observe("采集", "phase-1")
        record = observer.observe("处理", "phase-2")
        assert record is None

    def test_disabled_config_returns_none(self, tmp_path):
        working = tmp_path / "work"
        working.mkdir()
        (working / "a.txt").write_text("hello")
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        observer = FileChangeObserver(run_dir, working, FileObservationConfig(enabled=False))
        record = observer.observe("采集", "phase-1")
        assert record is None
        assert not (run_dir / "file_changes.jsonl").is_file()

    def test_exclude_patterns_skip_files(self, tmp_path):
        working = tmp_path / "work"
        working.mkdir()
        (working / "a.txt").write_text("hello")
        (working / "debug.log").write_text("log")
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        config = FileObservationConfig.from_meta({
            "file_observation": {"exclude": ["*.log"]}
        })
        observer = FileChangeObserver(run_dir, working, config)
        record = observer.observe("采集", "phase-1")

        assert record is not None
        paths = [c["path"] for c in record["changes"]]
        assert "a.txt" in paths
        assert "debug.log" not in paths

    def test_seq_strictly_increasing(self, tmp_path):
        working = tmp_path / "work"
        working.mkdir()
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        observer = FileChangeObserver(run_dir, working, FileObservationConfig())
        (working / "a.txt").write_text("1")
        r1 = observer.observe("采集", "phase-1")
        (working / "b.txt").write_text("2")
        r2 = observer.observe("处理", "phase-2")
        (working / "c.txt").write_text("3")
        r3 = observer.observe("归档", "phase-3")

        assert r1["seq"] == 1
        assert r2["seq"] == 2
        assert r3["seq"] == 3

    def test_records_appended_to_file_changes_jsonl(self, tmp_path):
        working = tmp_path / "work"
        working.mkdir()
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        observer = FileChangeObserver(run_dir, working, FileObservationConfig())
        (working / "a.txt").write_text("1")
        observer.observe("采集", "phase-1")
        (working / "b.txt").write_text("2")
        observer.observe("处理", "phase-2")

        fc_path = run_dir / "file_changes.jsonl"
        assert fc_path.is_file()
        lines = fc_path.read_text().strip().split("\n")
        assert len(lines) == 2
        r1 = json.loads(lines[0])
        r2 = json.loads(lines[1])
        assert r1["seq"] == 1 and r2["seq"] == 2

    def test_empty_working_dir_first_observe_returns_none(self, tmp_path):
        working = tmp_path / "work"
        working.mkdir()
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        observer = FileChangeObserver(run_dir, working, FileObservationConfig())
        record = observer.observe("采集", "phase-1")
        assert record is None

    def test_nested_directories_scanned(self, tmp_path):
        working = tmp_path / "work"
        (working / "src" / "deep" / "dir").mkdir(parents=True)
        (working / "src" / "deep" / "dir" / "file.py").write_text("code")
        run_dir = tmp_path / "run"
        run_dir.mkdir()

        observer = FileChangeObserver(run_dir, working, FileObservationConfig())
        record = observer.observe("采集", "phase-1")

        assert record is not None
        paths = [c["path"] for c in record["changes"]]
        assert "src/deep/dir/file.py" in paths
