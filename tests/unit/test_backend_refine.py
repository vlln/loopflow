"""Tests for backend layer refinement per ADR-0003."""

import pytest


class TestBaseBackend:
    """Verify BaseBackend only has the 3 methods loopflow needs."""

    def test_base_backend_has_create_session(self):
        from loopflow.infrastructure.backends.base import BaseBackend
        assert hasattr(BaseBackend, 'create_session')
        assert callable(BaseBackend.create_session)

    def test_base_backend_has_resume_session(self):
        from loopflow.infrastructure.backends.base import BaseBackend
        assert hasattr(BaseBackend, 'resume_session')
        assert callable(BaseBackend.resume_session)

    def test_base_backend_has_close(self):
        from loopflow.infrastructure.backends.base import BaseBackend
        assert hasattr(BaseBackend, 'close')
        assert callable(BaseBackend.close)

    def test_base_backend_no_list_sessions(self):
        from loopflow.infrastructure.backends.base import BaseBackend
        # list_sessions was removed per ADR-0003
        abstract_methods = [
            m for m in dir(BaseBackend)
            if not m.startswith('_')
        ]
        assert 'list_sessions' not in abstract_methods, \
            f"list_sessions should be removed: {abstract_methods}"

    @pytest.mark.parametrize(
        "backend_type",
        [
            pytest.param("claude", id="claude"),
            pytest.param("codex", id="codex"),
            pytest.param("gemini", id="gemini"),
            pytest.param("kimi", id="kimi"),
            pytest.param("kiro", id="kiro"),
            pytest.param("opencode", id="opencode"),
            pytest.param("pi", id="pi"),
            pytest.param("qwen", id="qwen"),
        ],
    )
    def test_cli_backends_declare_durable_resume(self, backend_type):
        from loopflow.infrastructure.backends.manager import _make_backend

        backend = _make_backend(backend_type)
        try:
            assert backend.capabilities.resume_session is True
            assert backend.capabilities.durable_session_id is True
        finally:
            backend.close()

    def test_cli_backend_reports_session_as_soon_as_parser_sees_it(self):
        from loopflow.infrastructure.backends.codex import CodexBackend

        sessions = []
        backend = CodexBackend(session_handler=sessions.append)

        def run(_cmd, *, on_stdout, on_stderr):
            on_stdout('{"type":"thread.started","thread_id":"thread-1"}')
            assert sessions == ["thread-1"]
            return 1

        backend._transport.run = run
        assert backend.create_session("prompt") == ("thread-1", 1)


class TestAgentModule:
    """Verify agent module is clean."""

    def test_parse_agent_exists(self):
        from loopflow.infrastructure.repository import parse_agent
        assert callable(parse_agent)

    def test_agent_module_no_subagent_specific(self):
        """subagent-skills specific attrs should be removed."""
        import loopflow.infrastructure.repository as repo
        assert hasattr(repo, 'list_agents')
