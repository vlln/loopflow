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


class TestAgentModule:
    """Verify agent module is clean."""

    def test_parse_agent_exists(self):
        from loopflow.infrastructure.repository import parse_agent
        assert callable(parse_agent)

    def test_agent_module_no_subagent_specific(self):
        """subagent-skills specific attrs should be removed."""
        import loopflow.infrastructure.repository as repo
        assert hasattr(repo, 'list_agents')