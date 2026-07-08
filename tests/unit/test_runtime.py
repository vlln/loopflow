"""Tests for workflow runtime per AC-001, AC-002, AC-004, AC-005, AC-006."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ── fixtures ──────────────────────────────────────────────────────────────

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

    def test_agent_failed_returns_none(self, temp_run_dir, mock_backend):
        from loopflow.runtime import RunContext, set_context, agent
        ctx = RunContext(run_dir=temp_run_dir)
        set_context(ctx)

        with patch('loopflow.runtime._make_backend', return_value=mock_backend):
            with patch('loopflow.runtime._run_subagent', return_value=(
                [{"type": "agent_done", "exit_code": 1}]
            )):
                result = agent("bad prompt")
                assert result is None

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

        def _mock_run(prompt, session, backend_name=None, model=None):
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

        def _mock_run(prompt, session, backend_name=None, model=None):
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
        def _mock_run(prompt, session, backend_name=None, model=None):
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

        def _mock_run(prompt, session, backend_name=None, model=None):
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