"""Backend compatibility re-exports — delegates to infrastructure.backends.

Kept for backward compatibility. New code should import from
loopflow.infrastructure.backends directly.
"""

from loopflow.infrastructure.backends.base import BaseBackend
from loopflow.infrastructure.backends.cli_backend import CliBackend
from loopflow.infrastructure.backends.acp_backend import AcpBackend
from loopflow.infrastructure.backends.claude import ClaudeBackend
from loopflow.infrastructure.backends.codex import CodexBackend
from loopflow.infrastructure.backends.gemini import GeminiBackend
from loopflow.infrastructure.backends.kimi import KimiBackend
from loopflow.infrastructure.backends.kiro import KiroBackend
from loopflow.infrastructure.backends.opencode import OpencodeBackend
from loopflow.infrastructure.backends.pi import PiBackend
from loopflow.infrastructure.backends.qwen import QwenBackend
from loopflow.infrastructure.backends.diagnostics import list_available_backends

__all__ = [
    "AcpBackend",
    "BaseBackend",
    "ClaudeBackend",
    "CliBackend",
    "CodexBackend",
    "GeminiBackend",
    "KimiBackend",
    "KiroBackend",
    "OpencodeBackend",
    "PiBackend",
    "QwenBackend",
    "list_available_backends",
]