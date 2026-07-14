"""Worktree isolation — git worktree creation (infrastructure layer)."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _create_worktree(run_id: str, seq: int) -> str | None:
    """Create a git worktree for isolated agent execution.

    Returns the worktree path, or None if not in a git repo.
    """
    worktree_name = f"lf_{run_id}_{seq}"
    worktree_path = Path.cwd() / ".agents" / "worktrees" / worktree_name
    try:
        subprocess.run(
            ["git", "worktree", "add", str(worktree_path)],
            capture_output=True, text=True, timeout=10, check=True,
        )
        return str(worktree_path)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None