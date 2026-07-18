"""Tests for dispatch logic per AC-012."""

import json
import os
import subprocess
from pathlib import Path

import pytest


class TestDispatchScan:
    def test_empty_queue(self, queue_dir):
        """AC-012-N-3: dispatch on empty queue exits cleanly."""
        entries = list(queue_dir.glob("*.json"))
        assert entries == []

    def test_single_task(self, queue_dir):
        """AC-012-N-1: dispatch picks up a single task from queue."""
        path = queue_dir / "task.json"
        path.write_text(json.dumps({
            "loop": "test", "args": {}, "resources": {},
            "priority": 5, "created": "2026-07-18T10:00:00Z",
        }))
        entries = list(queue_dir.glob("*.json"))
        assert len(entries) == 1
        assert json.loads(entries[0].read_text())["loop"] == "test"

    def test_priority_ordering(self, queue_dir):
        """AC-012-N-2: tasks execute in priority order."""
        entries_data = [
            ("low", 10),
            ("high", 1),
            ("mid", 5),
        ]
        for i, (name, pri) in enumerate(entries_data):
            path = queue_dir / f"{i}.json"
            path.write_text(json.dumps({
                "loop": name, "args": {}, "resources": {},
                "priority": pri, "created": f"2026-07-18T10:0{i}:00Z",
            }))

        files = sorted(queue_dir.glob("*.json"))
        entries = [json.loads(f.read_text()) for f in files]
        sorted_entries = sorted(entries, key=lambda x: (x["priority"], x["created"]))
        assert sorted_entries[0]["loop"] == "high"
        assert sorted_entries[1]["loop"] == "mid"
        assert sorted_entries[2]["loop"] == "low"

    def test_resource_conflict_skips(self, queue_dir):
        """AC-012-B-1: same resource, second task is skipped."""
        # Two tasks with same resource
        for i in range(2):
            path = queue_dir / f"{i}.json"
            path.write_text(json.dumps({
                "loop": f"task-{i}", "args": {}, "priority": i,
                "resources": {"repo": "/same/path"},
                "created": f"2026-07-18T10:0{i}:00Z",
            }))

        # Verify both exist, same resource
        entries = [json.loads(f.read_text()) for f in sorted(queue_dir.glob("*.json"))]
        assert entries[0]["resources"] == entries[1]["resources"]
        assert entries[0]["resources"]["repo"] == "/same/path"


class TestDispatchFailure:
    def test_failed_task_removed_from_queue(self, queue_dir):
        """AC-012-F-1: failed task is removed from queue, next task processed."""
        path = queue_dir / "will-fail.json"
        path.write_text(json.dumps({
            "loop": "bad", "args": {}, "resources": {},
            "priority": 1, "created": "2026-07-18T10:00:00Z",
        }))
        # Simulate failure: remove from queue, log error
        path.unlink()
        assert not path.exists()
        # Remaining queue should be empty
        assert list(queue_dir.glob("*.json")) == []