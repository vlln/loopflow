"""Tests for workflow runtime per AC-001, AC-002, AC-004, AC-005, AC-006."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ── fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_mock():
    """Reset mock mode before each test."""
    from loopflow.runtime import set_mock
    set_mock(None)
    yield
    set_mock(None)


@pytest.fixture
def temp_run_dir():
    d = Path(tempfile.mkdtemp()) / "test-run"
    d.mkdir(parents=True)
    yield d


@pytest.fixture
def mock_backend():
    """Mock backend that returns predictable results."""
    backend = MagicMock()
    backend.create_session.return_value = ("test-sid", 0)
    backend.resume_session.return_value = 0
    return backend


@pytest.fixture
def loop_with_output_agent(temp_run_dir):
    """Create a loop with an agent that has output schema."""
    loop_dir = Path(tempfile.mkdtemp()) / "test-loop"
    loop_dir.mkdir(parents=True)
    agents_dir = loop_dir / "agents"
    agents_dir.mkdir(parents=True)

    (agents_dir / "default.md").write_text("""---
name: default
description: Default agent
---
You are a helpful assistant. Answer concisely.
""")

    (agents_dir / "reporter.md").write_text("""---
name: reporter
description: Structured reporter
output:
  type: object
  properties:
    verdict:
      type: string
    score:
      type: number
  required:
    - verdict
    - score
---
You are a reporter. Return structured results.
""")
    return loop_dir


# ── RunContext ────────────────────────────────────────────────────────────

class TestRunContext:
    def test_init_creates_run_id(self):
        from loopflow.runtime import RunContext
        ctx = RunContext()
        assert ctx.run_id is not None
        assert len(ctx.run_id) == 8

    def test_init_with_explicit_run_id(self):
        from loopflow.runtime import RunContext
        ctx = RunContext(run_id="abc12345")
        assert ctx.run_id == "abc12345"

    def test_next_session_increments(self):
        from loopflow.runtime import RunContext
        ctx = RunContext()
        s1 = ctx.next_session()
        s2 = ctx.next_session()
        assert s1 == f"wf_{ctx.run_id}_1"
        assert s2 == f"wf_{ctx.run_id}_2"

    def test_resume_mode(self):
        from loopflow.runtime import RunContext
        ctx = RunContext(resume=True)
        assert ctx.resume is True


# ── agent() ───────────────────────────────────────────────────────────────

class TestAgent:
    def test_agent_returns_text(self, temp_run_dir, mock_backend):
        from loopflow.runtime import RunContext, set_context, agent
        ctx = RunContext(run_dir=temp_run_dir)
        set_context(ctx)

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', return_value=(
                [{"type": "agent_text", "content": "hello world"},
                 {"type": "agent_done", "exit_code": 0}]
            )):
                result = agent("say hello")
                assert result == "hello world"

    def test_agent_failed_raises_agent_error(self, temp_run_dir, mock_backend):
        from loopflow.runtime import RunContext, set_context, agent
        from loopflow.agent import AgentError
        ctx = RunContext(run_dir=temp_run_dir)
        set_context(ctx)

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', return_value=(
                [{"type": "agent_done", "exit_code": 1}]
            )):
                with pytest.raises(AgentError, match="exit code 1"):
                    agent("bad prompt")

    def test_agent_writes_cache(self, temp_run_dir, mock_backend):
        from loopflow.runtime import RunContext, set_context, agent
        ctx = RunContext(run_dir=temp_run_dir)
        set_context(ctx)

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', return_value=(
                [{"type": "agent_text", "content": "cached"},
                 {"type": "agent_done", "exit_code": 0}]
            )):
                agent("cache me")
                cache_path = temp_run_dir / "0001.jsonl"
                assert cache_path.exists()
                events = [json.loads(l) for l in cache_path.read_text().strip().split("\n") if l]
                assert any(e["type"] == "agent_done" and e["exit_code"] == 0 for e in events)

    def test_agent_resume_cache_hit(self, temp_run_dir):
        from loopflow.runtime import RunContext, set_context, agent
        # Pre-write cache
        cache_path = temp_run_dir / "0001.jsonl"
        cache_path.write_text(json.dumps({"type": "agent_text", "content": "cached"}) + "\n"
                            + json.dumps({"type": "agent_done", "exit_code": 0}) + "\n")

        ctx = RunContext(run_dir=temp_run_dir, resume=True)
        set_context(ctx)

        with patch('loopflow.runtime._run_subagent') as mock_run:
            result = agent("should be cached")
            assert result == "cached"
            mock_run.assert_not_called()

    def test_agent_resume_cache_miss(self, temp_run_dir, mock_backend):
        from loopflow.runtime import RunContext, set_context, agent
        ctx = RunContext(run_dir=temp_run_dir, resume=True)
        set_context(ctx)

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', return_value=(
                [{"type": "agent_text", "content": "fresh"},
                 {"type": "agent_done", "exit_code": 0}]
            )):
                result = agent("new prompt")
                assert result == "fresh"

    def test_agent_corrupted_cache_re_executes(self, temp_run_dir, mock_backend):
        from loopflow.runtime import RunContext, set_context, agent
        # Write corrupted cache
        cache_path = temp_run_dir / "0001.jsonl"
        cache_path.write_text("not valid json\n")

        ctx = RunContext(run_dir=temp_run_dir, resume=True)
        set_context(ctx)

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', return_value=(
                [{"type": "agent_text", "content": "recovered"},
                 {"type": "agent_done", "exit_code": 0}]
            )):
                result = agent("should re-execute")
                assert result == "recovered"


# ── parallel() ────────────────────────────────────────────────────────────

class TestParallel:
    def test_parallel_runs_all(self, temp_run_dir, mock_backend):
        from loopflow.runtime import RunContext, set_context, agent, parallel
        ctx = RunContext(run_dir=temp_run_dir)
        set_context(ctx)

        def _mock_run(prompt, session, backend_name=None, model=None, cwd=None, requires=None):
            return [
                {"type": "agent_text", "content": f"result:{prompt}"},
                {"type": "agent_done", "exit_code": 0},
            ]

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', side_effect=_mock_run):
                results = parallel([
                    lambda: agent("task a"),
                    lambda: agent("task b"),
                    lambda: agent("task c"),
                ])
                assert results == ["result:task a", "result:task b", "result:task c"]

    def test_parallel_empty(self, temp_run_dir):
        from loopflow.runtime import RunContext, set_context, parallel
        ctx = RunContext(run_dir=temp_run_dir)
        set_context(ctx)
        assert parallel([]) == []

    def test_parallel_failure_returns_none(self, temp_run_dir, mock_backend):
        from loopflow.runtime import RunContext, set_context, agent, parallel
        ctx = RunContext(run_dir=temp_run_dir)
        set_context(ctx)

        def _mock_run(prompt, session, backend_name=None, model=None, cwd=None, requires=None):
            if "fail" in prompt:
                raise Exception("boom")
            return [
                {"type": "agent_text", "content": f"result:{prompt}"},
                {"type": "agent_done", "exit_code": 0},
            ]

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', side_effect=_mock_run):
                results = parallel([
                    lambda: agent("a"),
                    lambda: agent("fail"),
                    lambda: agent("c"),
                ])
                assert results == ["result:a", None, "result:c"]


# ── pipeline() ────────────────────────────────────────────────────────────

class TestPipeline:
    def test_pipeline_processes_items(self, temp_run_dir, mock_backend):
        from loopflow.runtime import RunContext, set_context, agent, pipeline
        ctx = RunContext(run_dir=temp_run_dir)
        set_context(ctx)

        # Use a dict-based mock that returns content based on prompt
        def _mock_run(prompt, session, backend_name=None, model=None, cwd=None, requires=None):
            return [
                {"type": "agent_text", "content": f"result:{prompt}"},
                {"type": "agent_done", "exit_code": 0},
            ]

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', side_effect=_mock_run):
                results = pipeline(
                    ["a", "b"],
                    lambda item, idx: agent(f"analyze:{item}"),
                    lambda prev, item, idx: agent(f"fix:{item}"),
                )
                # Results come back in input order
                assert results[0] == "result:fix:a"
                assert results[1] == "result:fix:b"

    def test_pipeline_empty(self, temp_run_dir):
        from loopflow.runtime import RunContext, set_context, pipeline
        ctx = RunContext(run_dir=temp_run_dir)
        set_context(ctx)
        assert pipeline([], lambda x, i: x) == []

    def test_pipeline_none_skips_remaining(self, temp_run_dir, mock_backend):
        from loopflow.runtime import RunContext, set_context, agent, pipeline
        ctx = RunContext(run_dir=temp_run_dir)
        set_context(ctx)

        def _mock_run(prompt, session, backend_name=None, model=None, cwd=None, requires=None):
            return [
                {"type": "agent_done", "exit_code": 1},  # fails, returns None
            ]

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', side_effect=_mock_run):
                stage2_called = []

                def stage2(prev, item, idx):
                    stage2_called.append(item)
                    return "should not reach"

                results = pipeline(["a"], lambda item, idx: agent("fail"), stage2)
                assert results == [None]
                assert stage2_called == []  # stage2 skipped


# ── workflow() ────────────────────────────────────────────────────────────

class TestWorkflow:
    def test_workflow_nonexistent(self, temp_run_dir):
        from loopflow.runtime import RunContext, set_context, workflow
        ctx = RunContext(run_dir=temp_run_dir)
        set_context(ctx)
        result = workflow("/nonexistent/path.py")
        assert result is None


# ── phase tracking ──────────────────────────────────────────────────────────

class TestPhaseTracking:
    """A2: Agent events carry phase context."""

    def test_agent_event_has_phase_field(self, temp_run_dir, mock_backend):
        from loopflow.runtime import RunContext, set_context, phase, agent
        ctx = RunContext(run_dir=temp_run_dir)
        set_context(ctx)

        phase("Research")

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', return_value=(
                [{"type": "agent_text", "content": "ok"},
                 {"type": "agent_done", "exit_code": 0}]
            )):
                agent("do something")
                cache_path = temp_run_dir / "0001.jsonl"
                assert cache_path.exists()
                events = [json.loads(l) for l in cache_path.read_text().strip().split("\n") if l]
                start_events = [e for e in events if e["type"] == "agent_start"]
                assert len(start_events) == 1
                assert start_events[0]["phase"] == "Research"

    def test_agent_event_without_phase(self, temp_run_dir, mock_backend):
        """agent called before any phase() should have phase=None or omit field."""
        from loopflow.runtime import RunContext, set_context, agent
        ctx = RunContext(run_dir=temp_run_dir)
        set_context(ctx)

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', return_value=(
                [{"type": "agent_text", "content": "ok"},
                 {"type": "agent_done", "exit_code": 0}]
            )):
                agent("no phase")
                cache_path = temp_run_dir / "0001.jsonl"
                events = [json.loads(l) for l in cache_path.read_text().strip().split("\n") if l]
                start_events = [e for e in events if e["type"] == "agent_start"]
                assert len(start_events) == 1
                assert start_events[0].get("phase") is None

    def test_phase_change_updates_agent_events(self, temp_run_dir, mock_backend):
        from loopflow.runtime import RunContext, set_context, phase, agent
        ctx = RunContext(run_dir=temp_run_dir)
        set_context(ctx)

        phase("First")
        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', return_value=(
                [{"type": "agent_text", "content": "ok"},
                 {"type": "agent_done", "exit_code": 0}]
            )):
                agent("task 1")

        phase("Second")
        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', return_value=(
                [{"type": "agent_text", "content": "ok"},
                 {"type": "agent_done", "exit_code": 0}]
            )):
                agent("task 2")

        # Check first agent's phase
        cache1 = temp_run_dir / "0001.jsonl"
        events1 = [json.loads(l) for l in cache1.read_text().strip().split("\n") if l]
        start1 = [e for e in events1 if e["type"] == "agent_start"][0]
        assert start1["phase"] == "First"

        # Check second agent's phase
        cache2 = temp_run_dir / "0002.jsonl"
        events2 = [json.loads(l) for l in cache2.read_text().strip().split("\n") if l]
        start2 = [e for e in events2 if e["type"] == "agent_start"][0]
        assert start2["phase"] == "Second"


# ── agent_def ────────────────────────────────────────────────────────────────

class TestAgentDef:
    """A3: agent() accepts agent_def parameter to load agent definition files."""

    @pytest.fixture
    def loop_with_agents(self, temp_run_dir):
        """Create a temporary loop directory with agent definitions."""
        loop_dir = Path(tempfile.mkdtemp()) / "test-loop"
        loop_dir.mkdir(parents=True)
        agents_dir = loop_dir / "agents"
        agents_dir.mkdir(parents=True)

        # Create a translator agent definition
        (agents_dir / "translator.md").write_text("""---
name: translator
description: Professional translator
requires:
  params:
    - language
---
You are a professional translator. Translate the input to {{language}}.
""")

        # Create a default agent definition
        (agents_dir / "default.md").write_text("""---
name: default
description: Default agent
---
You are a helpful assistant. Answer concisely.
""")

        return loop_dir

    def test_agent_def_merges_body_and_prompt(self, temp_run_dir, mock_backend,
                                               loop_with_agents):
        from loopflow.runtime import RunContext, set_context, agent
        ctx = RunContext(run_dir=temp_run_dir, loop_dir=loop_with_agents)
        set_context(ctx)

        captured_prompt = []

        def _mock_run(prompt, session, backend_name=None, model=None, cwd=None, requires=None):
            captured_prompt.append(prompt)
            return [
                {"type": "agent_text", "content": "translated"},
                {"type": "agent_done", "exit_code": 0},
            ]

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', side_effect=_mock_run):
                agent("Hello world", agent_def="translator", language="Chinese")

        assert len(captured_prompt) == 1
        assert "professional translator" in captured_prompt[0]
        assert "Chinese" in captured_prompt[0]
        assert "Hello world" in captured_prompt[0]

    def test_agent_def_default(self, temp_run_dir, mock_backend, loop_with_agents):
        """agent_def defaults to 'default' when available."""
        from loopflow.runtime import RunContext, set_context, agent
        ctx = RunContext(run_dir=temp_run_dir, loop_dir=loop_with_agents)
        set_context(ctx)

        captured_prompt = []

        def _mock_run(prompt, session, backend_name=None, model=None, cwd=None, requires=None):
            captured_prompt.append(prompt)
            return [
                {"type": "agent_text", "content": "ok"},
                {"type": "agent_done", "exit_code": 0},
            ]

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', side_effect=_mock_run):
                agent("test")

        assert len(captured_prompt) == 1
        assert "helpful assistant" in captured_prompt[0]
        assert "test" in captured_prompt[0]

    def test_agent_def_without_loop_dir(self, temp_run_dir, mock_backend):
        """Without loop_dir, agent_def is ignored and works as plain prompt."""
        from loopflow.runtime import RunContext, set_context, agent
        ctx = RunContext(run_dir=temp_run_dir)  # no loop_dir
        set_context(ctx)

        captured_prompt = []

        def _mock_run(prompt, session, backend_name=None, model=None, cwd=None, requires=None):
            captured_prompt.append(prompt)
            return [
                {"type": "agent_text", "content": "ok"},
                {"type": "agent_done", "exit_code": 0},
            ]

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', side_effect=_mock_run):
                agent("plain prompt", agent_def="translator")

        assert len(captured_prompt) == 1
        assert captured_prompt[0] == "plain prompt"

    def test_agent_def_nonexistent(self, temp_run_dir, mock_backend,
                                    loop_with_agents):
        """Non-existent agent_def falls back to plain prompt."""
        from loopflow.runtime import RunContext, set_context, agent
        ctx = RunContext(run_dir=temp_run_dir, loop_dir=loop_with_agents)
        set_context(ctx)

        captured_prompt = []

        def _mock_run(prompt, session, backend_name=None, model=None, cwd=None, requires=None):
            captured_prompt.append(prompt)
            return [
                {"type": "agent_text", "content": "ok"},
                {"type": "agent_done", "exit_code": 0},
            ]

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', side_effect=_mock_run):
                agent("test", agent_def="nonexistent")

        assert len(captured_prompt) == 1
        assert captured_prompt[0] == "test"

    def test_agent_def_missing_template_param(self, temp_run_dir, mock_backend,
                                                loop_with_agents):
        """Missing template param raises ValueError."""
        from loopflow.runtime import RunContext, set_context, agent
        ctx = RunContext(run_dir=temp_run_dir, loop_dir=loop_with_agents)
        set_context(ctx)

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with pytest.raises(ValueError, match="language"):
                agent("Hello", agent_def="translator")  # missing language=


# ── output schema ─────────────────────────────────────────────────────────────

class TestOutputSchema:
    """Auto-detect output schema from agent definition, prompt injection, retry."""

    def test_auto_schema_from_agent_def(self, temp_run_dir, mock_backend,
                                         loop_with_output_agent):
        """Agent definition with output → agent() returns dict."""
        from loopflow.runtime import RunContext, set_context, agent
        ctx = RunContext(run_dir=temp_run_dir, loop_dir=loop_with_output_agent)
        set_context(ctx)

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', return_value=(
                [{"type": "agent_text",
                  "content": '{"verdict": "PASS", "score": 95}'},
                 {"type": "agent_done", "exit_code": 0}]
            )):
                result = agent("Report results", agent_def="reporter")
                assert isinstance(result, dict)
                assert result["verdict"] == "PASS"
                assert result["score"] == 95

    def test_explicit_schema_overrides_output(self, temp_run_dir, mock_backend,
                                               loop_with_output_agent):
        """Explicit schema= overrides agent definition output."""
        from loopflow.runtime import RunContext, set_context, agent
        ctx = RunContext(run_dir=temp_run_dir, loop_dir=loop_with_output_agent)
        set_context(ctx)

        explicit_schema = {"type": "object", "properties": {"custom": {"type": "string"}}}

        captured_prompt = []
        def _mock_run(prompt, session, backend_name=None, model=None, cwd=None, requires=None):
            captured_prompt.append(prompt)
            return [
                {"type": "agent_text", "content": '{"custom": "override"}'},
                {"type": "agent_done", "exit_code": 0},
            ]

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', side_effect=_mock_run):
                result = agent("test", agent_def="reporter", schema=explicit_schema)
                assert result == {"custom": "override"}
                # Explicit schema should be in the prompt, not the agent's output
                assert '"custom"' in captured_prompt[0]

    def test_schema_injected_into_prompt(self, temp_run_dir, mock_backend,
                                          loop_with_output_agent):
        """Schema is injected into the prompt for the agent to see."""
        from loopflow.runtime import RunContext, set_context, agent
        ctx = RunContext(run_dir=temp_run_dir, loop_dir=loop_with_output_agent)
        set_context(ctx)

        captured_prompt = []
        def _mock_run(prompt, session, backend_name=None, model=None, cwd=None, requires=None):
            captured_prompt.append(prompt)
            return [
                {"type": "agent_text",
                  "content": '{"verdict": "PASS", "score": 90}'},
                {"type": "agent_done", "exit_code": 0},
            ]

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', side_effect=_mock_run):
                agent("test", agent_def="reporter")

        assert len(captured_prompt) == 1
        prompt = captured_prompt[0]
        assert "Output format" in prompt
        assert "JSON object" in prompt
        assert "verdict" in prompt
        assert "score" in prompt
        assert "Do NOT wrap" in prompt

    def test_schema_retry_on_json_error(self, temp_run_dir, mock_backend,
                                         loop_with_output_agent):
        """JSON parse failure triggers retry, succeeds on second attempt."""
        from loopflow.runtime import RunContext, set_context, agent
        ctx = RunContext(run_dir=temp_run_dir, loop_dir=loop_with_output_agent)
        set_context(ctx)

        call_count = [0]
        def _mock_run(prompt, session, backend_name=None, model=None, cwd=None, requires=None):
            call_count[0] += 1
            if call_count[0] == 1:
                # First attempt: invalid JSON (missing closing brace)
                return [
                    {"type": "agent_text", "content": '{"verdict": "PASS"'},
                    {"type": "agent_done", "exit_code": 0},
                ]
            else:
                # Second attempt: valid JSON
                return [
                    {"type": "agent_text",
                      "content": '{"verdict": "PASS", "score": 85}'},
                    {"type": "agent_done", "exit_code": 0},
                ]

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', side_effect=_mock_run):
                result = agent("test", agent_def="reporter")
                assert call_count[0] == 2
                assert result == {"verdict": "PASS", "score": 85}

    def test_schema_retry_raises_after_max_retries(self, temp_run_dir, mock_backend,
                                                    loop_with_output_agent):
        """After max_retries failed JSON attempts, raises AgentError."""
        from loopflow.runtime import RunContext, set_context, agent
        from loopflow.agent import AgentError
        ctx = RunContext(run_dir=temp_run_dir, loop_dir=loop_with_output_agent)
        set_context(ctx)

        call_count = [0]
        def _mock_run(prompt, session, backend_name=None, model=None, cwd=None, requires=None):
            call_count[0] += 1
            return [
                {"type": "agent_text", "content": "not valid json at all"},
                {"type": "agent_done", "exit_code": 0},
            ]

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', side_effect=_mock_run):
                with pytest.raises(AgentError, match="valid JSON"):
                    agent("test", agent_def="reporter", max_retries=2)

        # 1 initial + 2 retries = 3 attempts
        assert call_count[0] == 3

    def test_no_schema_injection_without_output(self, temp_run_dir, mock_backend,
                                                  loop_with_output_agent):
        """Agent without output field → no schema injection, returns string."""
        from loopflow.runtime import RunContext, set_context, agent
        ctx = RunContext(run_dir=temp_run_dir, loop_dir=loop_with_output_agent)
        set_context(ctx)

        captured_prompt = []
        def _mock_run(prompt, session, backend_name=None, model=None, cwd=None, requires=None):
            captured_prompt.append(prompt)
            return [
                {"type": "agent_text", "content": "plain text"},
                {"type": "agent_done", "exit_code": 0},
            ]

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', side_effect=_mock_run):
                result = agent("test", agent_def="default")

        assert result == "plain text"
        assert "Output format" not in captured_prompt[0]


# ── state ─────────────────────────────────────────────────────────────────────

class TestState:
    """State object with attribute access and persistence."""

    def test_state_create_with_defaults(self):
        from loopflow.runtime import State
        state = State({"attempt": 0, "mode": "test"})
        assert state.attempt == 0
        assert state.mode == "test"

    def test_state_set_and_get(self):
        from loopflow.runtime import State
        state = State({"attempt": 0})
        state.attempt = 5
        assert state.attempt == 5

    def test_state_to_dict(self):
        from loopflow.runtime import State
        state = State({"attempt": 0, "mode": "test"})
        state.attempt = 3
        d = state.to_dict()
        assert d == {"attempt": 3, "mode": "test"}

    def test_state_from_dict(self):
        from loopflow.runtime import State
        state = State.from_dict({"attempt": 5}, {"attempt": 0, "mode": "test"})
        # attempt from saved data takes precedence
        assert state.attempt == 5
        # mode from defaults fills in missing key
        assert state.mode == "test"

    def test_state_persisted_after_agent(self, temp_run_dir, mock_backend):
        from loopflow.runtime import RunContext, State, set_context, agent
        state = State({"attempt": 0})
        ctx = RunContext(run_dir=temp_run_dir, state=state)
        set_context(ctx)

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', return_value=(
                [{"type": "agent_text", "content": "ok"},
                 {"type": "agent_done", "exit_code": 0}]
            )):
                state.attempt = 1
                agent("test")

        state_path = temp_run_dir / "state.json"
        assert state_path.exists()
        saved = json.loads(state_path.read_text())
        assert saved["attempt"] == 1

    def test_state_no_persist_without_declaration(self, temp_run_dir, mock_backend):
        """Without state in RunContext, no state.json is created."""
        from loopflow.runtime import RunContext, set_context, agent
        ctx = RunContext(run_dir=temp_run_dir)  # no state
        set_context(ctx)

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', return_value=(
                [{"type": "agent_text", "content": "ok"},
                 {"type": "agent_done", "exit_code": 0}]
            )):
                agent("test")

        state_path = temp_run_dir / "state.json"
        assert not state_path.exists()


# ── mock auto ─────────────────────────────────────────────────────────────────

class TestMockAuto:
    """Auto mock mode generates data from schema."""

    def test_mock_auto_without_schema(self, temp_run_dir):
        from loopflow.runtime import RunContext, set_context, set_mock, agent
        set_mock("auto")
        ctx = RunContext(run_dir=temp_run_dir)
        set_context(ctx)

        result = agent("test")
        assert result == "mock response"

    def test_mock_auto_with_schema(self, temp_run_dir):
        from loopflow.runtime import RunContext, set_context, set_mock, agent
        set_mock("auto")
        ctx = RunContext(run_dir=temp_run_dir)
        set_context(ctx)

        schema = {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": ["PASS", "FAIL"]},
                "score": {"type": "number"},
                "tags": {"type": "array"},
            },
            "required": ["verdict", "score"],
        }
        result = agent("test", schema=schema)
        assert result == {"verdict": "PASS", "score": 0, "tags": []}

    def test_mock_auto_first_enum(self, temp_run_dir):
        from loopflow.runtime import RunContext, set_context, set_mock, agent
        set_mock("auto")
        ctx = RunContext(run_dir=temp_run_dir)
        set_context(ctx)

        schema = {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": ["REPRODUCED", "PARTIAL", "FAILED"]},
            },
        }
        result = agent("test", schema=schema)
        assert result == {"status": "REPRODUCED"}

    def test_mock_auto_nested_object(self, temp_run_dir):
        from loopflow.runtime import RunContext, set_context, set_mock, agent
        set_mock("auto")
        ctx = RunContext(run_dir=temp_run_dir)
        set_context(ctx)

        schema = {
            "type": "object",
            "properties": {
                "dimension_scores": {
                    "type": "object",
                    "properties": {
                        "data": {"type": "number"},
                        "process": {"type": "number"},
                    },
                },
            },
        }
        result = agent("test", schema=schema)
        assert result == {"dimension_scores": {"data": 0, "process": 0}}

    def test_mock_auto_with_agent_def_output(self, temp_run_dir,
                                               loop_with_output_agent):
        from loopflow.runtime import RunContext, set_context, set_mock, agent
        set_mock("auto")
        ctx = RunContext(run_dir=temp_run_dir, loop_dir=loop_with_output_agent)
        set_context(ctx)

        result = agent("test", agent_def="reporter")
        assert isinstance(result, dict)
        assert result["verdict"] == "mock response"
        assert result["score"] == 0