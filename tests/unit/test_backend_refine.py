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
            pytest.param("grok", id="grok"),
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

    def test_gork_typo_is_not_a_backend(self):
        from loopflow.infrastructure.backends.manager import _make_backend

        with pytest.raises(SystemExit):
            _make_backend("gork")

    def test_backend_install_guide_does_not_list_gork_typo(self):
        from loopflow.infrastructure.backends.diagnostics import format_install_guide

        guide = format_install_guide()
        assert "grok" in guide
        assert "gork" not in guide
        assert format_install_guide("gork") == "Unknown backend 'gork'."

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

    def test_grok_backend_parses_streaming_json(self):
        from loopflow.infrastructure.backends.grok import GrokBackend

        thoughts = []
        sessions = []
        texts = []
        backend = GrokBackend(text_handler=texts.append, thought_handler=thoughts.append, session_handler=sessions.append)

        def run(cmd, *, on_stdout, on_stderr):
            assert cmd[:5] == ["grok", "-p", "prompt", "--output-format", "streaming-json"]
            assert "--permission-mode" in cmd
            on_stdout('{"type":"text","data":"hello"}')
            on_stdout('{"type":"thought","data":"thinking"}')
            on_stdout('{"type":"end","sessionId":"session-1","stopReason":"EndTurn"}')
            return 0

        backend._selected._transport.run = run
        assert backend.create_session("prompt") == ("session-1", 0)
        assert texts == ["hello"]
        assert thoughts == ["thinking"]
        assert sessions == ["session-1"]

    def test_grok_backend_acp_uses_stdio_agent_and_meta(self):
        from loopflow.infrastructure.backends.grok import GrokBackend

        texts = []
        thoughts = []
        sessions = []
        backend = GrokBackend(transport="acp", text_handler=texts.append, thought_handler=thoughts.append, session_handler=sessions.append)
        assert backend._selected._transport._command == ["grok", "agent", "stdio"]

        calls = []
        backend._selected._ensure_initialized = lambda: None

        def call(method, params):
            calls.append((method, params))
            if method == "session/new":
                return {"sessionId": "grok-acp-1"}
            return {}

        backend._selected._transport.call = call

        assert backend.create_session("prompt", system="rules", model="grok-build") == ("grok-acp-1", 0)
        assert sessions == ["grok-acp-1"]
        assert calls[0][0] == "session/new"
        assert calls[0][1]["_meta"] == {"rules": "rules"}
        assert calls[1] == ("session/set_model", {"sessionId": "grok-acp-1", "modelId": "grok-build"})
        assert calls[2] == (
            "session/prompt",
            {"sessionId": "grok-acp-1", "prompt": [{"type": "text", "text": "prompt"}]},
        )

        backend._selected._on_update({"update": {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "hello"}}})
        backend._selected._on_update({"sessionUpdate": {"sessionUpdate": "agent_thought_chunk", "content": {"type": "text", "text": "thinking"}}})
        assert texts == ["hello"]
        assert thoughts == ["thinking"]

    def test_grok_backend_acp_resume_uses_system_override_meta(self):
        from loopflow.infrastructure.backends.grok import GrokBackend

        backend = GrokBackend(transport="acp")
        backend._selected._ensure_initialized = lambda: None
        calls = []

        def call(method, params):
            calls.append((method, params))
            return {}

        backend._selected._transport.call = call

        assert backend.resume_session("grok-acp-1", "next", system="system", system_mode="overwrite") == 0
        assert calls[0][0] == "session/load"
        assert calls[0][1]["sessionId"] == "grok-acp-1"
        assert calls[0][1]["_meta"] == {"systemPromptOverride": "system"}
        assert calls[1] == (
            "session/prompt",
            {"sessionId": "grok-acp-1", "prompt": [{"type": "text", "text": "next"}]},
        )


class TestAgentModule:
    """Verify agent module is clean."""

    def test_parse_agent_exists(self):
        from loopflow.infrastructure.repository import parse_agent
        assert callable(parse_agent)

    def test_agent_module_no_subagent_specific(self):
        """subagent-skills specific attrs should be removed."""
        import loopflow.infrastructure.repository as repo
        assert hasattr(repo, 'list_agents')


class TestAcpBackend:
    def test_acp_backend_reuses_transport_initialize_result(self):
        from loopflow.infrastructure.backends.acp_backend import AcpBackend

        backend = AcpBackend(["agent", "stdio"])
        calls = []

        def start():
            backend._transport._initialize_result = {"authMethods": [{"id": "cached_token"}]}

        def call(method, params):
            calls.append((method, params))
            if method == "session/new":
                return {"sessionId": "acp-1"}
            return {}

        backend._transport.start = start
        backend._transport.call = call

        assert backend.create_session("prompt") == ("acp-1", 0)
        assert [method for method, _ in calls] == ["session/new", "session/prompt"]
        assert backend._auth_methods == [{"id": "cached_token"}]
