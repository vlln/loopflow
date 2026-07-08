"""Tests for backend layer refinement per ADR-0003."""

import pytest


class TestBaseBackend:
    """Verify BaseBackend only has the 3 methods loopflow needs."""

    def test_base_backend_has_create_session(self):
        from loopflow.backends.base import BaseBackend
        assert hasattr(BaseBackend, 'create_session')
        assert callable(BaseBackend.create_session)

    def test_base_backend_has_resume_session(self):
        from loopflow.backends.base import BaseBackend
        assert hasattr(BaseBackend, 'resume_session')
        assert callable(BaseBackend.resume_session)

    def test_base_backend_has_close(self):
        from loopflow.backends.base import BaseBackend
        assert hasattr(BaseBackend, 'close')
        assert callable(BaseBackend.close)

    def test_base_backend_no_list_sessions(self):
        from loopflow.backends.base import BaseBackend
        # list_sessions was removed per ADR-0003
        abstract_methods = [
            m for m in dir(BaseBackend)
            if not m.startswith('_')
        ]
        assert 'list_sessions' not in abstract_methods, \
            f"list_sessions should be removed: {abstract_methods}"


class TestRegistry:
    """Verify registry has no goal/swarm/send/cancel/queue methods."""

    def test_registry_has_core_methods(self):
        from loopflow import registry
        assert hasattr(registry, 'register')
        assert hasattr(registry, 'get_session_id')
        assert hasattr(registry, 'get_session_status')
        assert hasattr(registry, 'complete')

    def test_registry_no_goal(self):
        from loopflow import registry
        assert not hasattr(registry, 'set_goal'), "set_goal should be removed"
        assert not hasattr(registry, 'get_goal'), "get_goal should be removed"
        assert not hasattr(registry, 'cancel_goal'), "cancel_goal should be removed"

    def test_registry_no_swarm(self):
        from loopflow import registry
        assert not hasattr(registry, 'swarm'), "swarm should be removed"

    def test_registry_no_queue(self):
        from loopflow import registry
        assert not hasattr(registry, 'enqueue_task'), "enqueue_task should be removed"
        assert not hasattr(registry, 'dequeue_task'), "dequeue_task should be removed"
        assert not hasattr(registry, 'cancel_task'), "cancel_task should be removed"
        assert not hasattr(registry, 'has_active_queue'), "has_active_queue should be removed"


class TestAgentModule:
    """Verify agent module is clean."""

    def test_parse_agent_exists(self):
        from loopflow.agent import parse_agent
        assert callable(parse_agent)

    def test_agent_module_no_subagent_specific(self):
        """subagent-skills specific attrs should be removed."""
        import loopflow.agent as agent
        # list_agents should remain (used by discovery)
        assert hasattr(agent, 'list_agents')