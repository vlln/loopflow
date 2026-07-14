"""Infrastructure layer — backends, transports, repository, context, worktree.

Technical implementations of I/O, file system, subprocess, caching.
Depends on domain layer for entity definitions.
"""

from loopflow.infrastructure.backends.base import BaseBackend

__all__ = ["BaseBackend"]