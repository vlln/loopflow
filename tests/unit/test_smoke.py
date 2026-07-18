"""Smoke tests for loopflow package."""


def test_import():
    import loopflow
    assert loopflow.__version__ == "0.17.1"


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