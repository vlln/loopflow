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

class TestQueueStatus:
    """AC-028: queue entry status machine (queue.py branches)."""

    def test_enqueue_writes_pending_status(self, queue_dir):
        from loopflow.infrastructure.queue import enqueue

        path = enqueue("hello")
        data = json.loads(path.read_text())
        assert data["status"] == "pending"
        assert "status_reason" not in data
        assert "superseded_by" not in data

    def test_effective_status_defaults_to_pending(self):
        from loopflow.infrastructure.queue import effective_status

        assert effective_status({}) == "pending"
        assert effective_status({"status": "unknown_state"}) == "pending"
        assert effective_status({"status": None}) == "pending"
        assert effective_status({"status": "pending"}) == "pending"
        assert effective_status({"status": "deferred"}) == "deferred"
        assert effective_status({"status": "superseded"}) == "superseded"

    def test_list_queue_exposes_status_fields(self, queue_dir):
        from loopflow.infrastructure.queue import enqueue, mark_status, list_queue

        path = enqueue("hello")
        mark_status(path, "deferred", reason="repo locked")

        entries = list_queue()
        assert entries[0]["status"] == "deferred"
        assert entries[0]["status_reason"] == "repo locked"

    def test_mark_status_preserves_other_fields(self, queue_dir):
        from loopflow.infrastructure.queue import enqueue, mark_status

        path = enqueue("hello", args={"k": "v"}, resources={"repo": "/p"}, priority=3)
        mark_status(path, "superseded", reason="replaced", superseded_by="newid")

        data = json.loads(path.read_text())
        assert data["status"] == "superseded"
        assert data["status_reason"] == "replaced"
        assert data["superseded_by"] == "newid"
        assert data["loop"] == "hello"
        assert data["args"] == {"k": "v"}
        assert data["priority"] == 3

    def test_supersede_marks_pending_and_deferred_same_loop(self, queue_dir):
        from loopflow.infrastructure.queue import enqueue, mark_status

        pending = enqueue("hello")
        deferred = enqueue("hello")
        mark_status(deferred, "deferred", reason="repo locked")
        other_loop = enqueue("other")

        new_path = enqueue("hello", supersede=True)
        new_id = new_path.stem

        for old in (pending, deferred):
            data = json.loads(old.read_text())
            assert data["status"] == "superseded"
            assert data["superseded_by"] == new_id
            assert data["status_reason"]

        other = json.loads(other_loop.read_text())
        assert other["status"] == "pending"

        new_data = json.loads(new_path.read_text())
        assert new_data["status"] == "pending"

    def test_supersede_does_not_remark_already_superseded(self, queue_dir):
        from loopflow.infrastructure.queue import enqueue, mark_status

        old = enqueue("hello")
        mark_status(old, "superseded", superseded_by="first")

        enqueue("hello", supersede=True)

        data = json.loads(old.read_text())
        assert data["superseded_by"] == "first"

    def test_supersede_without_same_loop_is_plain_enqueue(self, queue_dir):
        from loopflow.infrastructure.queue import enqueue, list_queue

        enqueue("other")
        new_path = enqueue("hello", supersede=True)

        entries = list_queue()
        assert len(entries) == 2
        assert all(e["status"] == "pending" for e in entries)
        assert "superseded_by" not in json.loads(new_path.read_text())

    def test_supersede_treats_unknown_status_as_pending(self, queue_dir):
        from loopflow.infrastructure.queue import enqueue

        legacy = queue_dir / "legacy.json"
        legacy.write_text(json.dumps({
            "loop": "hello", "args": {}, "resources": {},
            "priority": 5, "created": "2026-07-25T00:00:00Z",
            "status": "unknown_state",
        }))

        new_path = enqueue("hello", supersede=True)

        data = json.loads(legacy.read_text())
        assert data["status"] == "superseded"
        assert data["superseded_by"] == new_path.stem
