"""Smoke tests for loopflow package."""

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 has no tomllib (3.11+)
    tomllib = None


def test_import():
    import loopflow

    text = Path("pyproject.toml").read_text(encoding="utf-8")
    if tomllib is not None:
        version = tomllib.loads(text)["project"]["version"]
    else:
        import re

        version = re.search(r'(?m)^version = "([^"]+)"', text).group(1)
    assert loopflow.__version__ == version


def test_backends_exist():
    from loopflow.infrastructure.backends import base, claude, kimi, codex, gemini, kiro, opencode, pi, qwen
    assert base.BaseBackend is not None


def test_transports_exist():
    from loopflow.infrastructure.transports import cli as cli_transport
    assert cli_transport.CliTransport is not None


def test_agent_module():
    from loopflow.infrastructure.repository import parse_agent
    assert callable(parse_agent)


def test_lock_module():
    from loopflow.infrastructure.lock import acquire, release, check
    assert callable(acquire)
    assert callable(release)
    assert callable(check)
