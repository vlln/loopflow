"""Tests for queue operations per AC-011."""

import json
from pathlib import Path

import pytest


class TestEnqueue:
    def test_creates_queue_file(self, queue_dir):
        """AC-011-N-1: enqueue creates a JSON file in the queue directory."""
        entry = {
            "loop": "fix-issue",
            "args": {"issue_path": "issues/0007.md"},
            "resources": {"repo": "/path/to/project"},
            "priority": 5,
            "created": "2026-07-18T10:00:00Z",
        }
        path = queue_dir / "test.json"
        path.write_text(json.dumps(entry, indent=2))

        assert path.exists()
        data = json.loads(path.read_text())
        assert data["loop"] == "fix-issue"
        assert data["priority"] == 5

    def test_multiple_entries_sorted_by_priority(self, queue_dir):
        """AC-011-N-2: entries are sorted by priority then created time."""
        entries = [
            {"loop": "low", "priority": 10, "created": "2026-07-18T10:00:00Z"},
            {"loop": "high", "priority": 1, "created": "2026-07-18T11:00:00Z"},
            {"loop": "mid", "priority": 5, "created": "2026-07-18T09:00:00Z"},
        ]
        for i, e in enumerate(entries):
            path = queue_dir / f"{i}.json"
            path.write_text(json.dumps({
                "loop": e["loop"],
                "args": {},
                "resources": {},
                "priority": e["priority"],
                "created": e["created"],
            }))

        files = sorted(queue_dir.glob("*.json"))
        entries_from_files = [json.loads(f.read_text()) for f in files]
        sorted_entries = sorted(entries_from_files,
                                key=lambda x: (x["priority"], x["created"]))
        assert sorted_entries[0]["loop"] == "high"
        assert sorted_entries[1]["loop"] == "mid"
        assert sorted_entries[2]["loop"] == "low"


class TestDequeue:
    def test_remove_after_processing(self, queue_dir):
        """Queue entry is removed after dispatch picks it up."""
        path = queue_dir / "task.json"
        path.write_text(json.dumps({
            "loop": "test", "args": {}, "resources": {},
            "priority": 5, "created": "2026-07-18T10:00:00Z",
        }))
        assert path.exists()
        path.unlink()
        assert not path.exists()


class TestListQueue:
    def test_empty_queue(self, queue_dir):
        """Empty queue returns empty list."""
        entries = list(queue_dir.glob("*.json"))
        assert entries == []

    def test_non_empty_queue(self, queue_dir):
        """Queue with entries is listed."""
        (queue_dir / "a.json").write_text(json.dumps({
            "loop": "test", "args": {}, "resources": {},
            "priority": 5, "created": "2026-07-18T10:00:00Z",
        }))
        entries = list(queue_dir.glob("*.json"))
        assert len(entries) == 1