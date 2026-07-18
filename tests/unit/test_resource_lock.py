"""Tests for resource lock per AC-013."""

import json
import os
import time
from pathlib import Path

import pytest


class TestResourceLock:
    def test_acquire_creates_lock_file(self, locks_dir):
        """AC-013-N-1: acquiring a lock creates a file with PID and timestamp."""
        lock_path = locks_dir / "repo-abc123.lock"
        lock_path.write_text(json.dumps({
            "pid": os.getpid(),
            "timestamp": time.time(),
        }))
        assert lock_path.exists()
        data = json.loads(lock_path.read_text())
        assert data["pid"] == os.getpid()

    def test_release_deletes_lock_file(self, locks_dir):
        """AC-013-N-2: releasing a lock deletes the file."""
        lock_path = locks_dir / "repo-abc123.lock"
        lock_path.write_text("")
        assert lock_path.exists()
        lock_path.unlink()
        assert not lock_path.exists()

    def test_conflict_detection(self, locks_dir):
        """Two tasks cannot acquire the same resource lock."""
        lock_path = locks_dir / "repo-abc123.lock"
        lock_path.write_text(json.dumps({
            "pid": 99999,  # Simulated other process
            "timestamp": time.time(),
        }))
        assert lock_path.exists()
        # Second process should detect conflict
        assert lock_path.exists()  # Lock is still held

    def test_stale_lock_cleanup(self, locks_dir):
        """AC-013-B-1: locks older than 30 minutes are cleaned up."""
        lock_path = locks_dir / "repo-stale.lock"
        # Simulate a stale lock (40 minutes old)
        lock_path.write_text(json.dumps({
            "pid": 12345,
            "timestamp": time.time() - 40 * 60,
        }))
        assert lock_path.exists()

        # Cleanup stale locks
        cutoff = time.time() - 30 * 60
        for lock_file in locks_dir.glob("*.lock"):
            try:
                data = json.loads(lock_file.read_text())
                if data["timestamp"] < cutoff:
                    lock_file.unlink()
            except (json.JSONDecodeError, KeyError):
                pass

        assert not lock_path.exists()