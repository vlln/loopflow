"""Tests for loop discovery per AC-007."""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def loops_dir():
    d = Path(tempfile.mkdtemp()) / "loops"
    d.mkdir(parents=True)
    old = None
    import os
    # Override LOOPS_DIR for testing
    old = os.environ.get("LOOPFLOW_LOOPS_DIR")
    os.environ["LOOPFLOW_LOOPS_DIR"] = str(d)
    yield d
    if old:
        os.environ["LOOPFLOW_LOOPS_DIR"] = old
    else:
        del os.environ["LOOPFLOW_LOOPS_DIR"]


def _create_loop(loops_dir: Path, name: str, meta: dict, agents: list[dict] = None):
    """Helper to create a valid loop directory."""
    loop_dir = loops_dir / name
    loop_dir.mkdir(parents=True)

    # Write workflow.py
    meta_str = "meta = " + repr(meta)
    wf_content = f"""{meta_str}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    return agent("hello")
"""
    (loop_dir / "workflow.py").write_text(wf_content)

    # Write agents
    if agents:
        agents_dir = loop_dir / "agents"
        agents_dir.mkdir(parents=True)
        for a in agents:
            body = a.get("body", "")
            env_str = ""
            if "env" in a:
                env_str = "env:\n" + "".join(f"  - {e}\n" for e in a["env"])
            skills_str = ""
            if "skills" in a:
                skills_str = "skills:\n" + "".join(f"  - {s}\n" for s in a["skills"])
            mcp_str = ""
            if "mcpServers" in a:
                mcp_str = "mcpServers:\n" + "".join(f"  - {m}\n" for m in a["mcpServers"])
            agent_content = f"""---
name: {a['name']}
description: {a['description']}
{env_str}{skills_str}{mcp_str}---
{body}
"""
            (agents_dir / f"{a['name']}.md").write_text(agent_content)


class TestListLoops:
    def test_empty_directory(self, loops_dir):
        from loopflow.discovery import list_loops
        result = list_loops()
        assert result == []

    def test_single_loop(self, loops_dir):
        _create_loop(loops_dir, "hello", {"name": "hello", "description": "A test loop"})
        from loopflow.discovery import list_loops
        result = list_loops()
        assert len(result) == 1
        assert result[0][0] == "hello"
        assert result[0][1]["name"] == "hello"

    def test_multiple_loops(self, loops_dir):
        _create_loop(loops_dir, "loop-a", {"name": "loop-a", "description": "First"})
        _create_loop(loops_dir, "loop-b", {"name": "loop-b", "description": "Second"})
        from loopflow.discovery import list_loops
        result = list_loops()
        assert len(result) == 2


class TestLoadLoop:
    def test_load_valid_loop(self, loops_dir):
        _create_loop(loops_dir, "hello", {"name": "hello", "description": "A test loop"})
        from loopflow.discovery import load_loop
        mod, meta, loop_dir = load_loop("hello")
        assert meta["name"] == "hello"
        assert hasattr(mod, "run")
        assert loop_dir.is_dir()

    def test_load_missing_workflow(self, loops_dir):
        loop_dir = loops_dir / "empty"
        loop_dir.mkdir(parents=True)
        from loopflow.discovery import load_loop
        with pytest.raises(SystemExit):
            load_loop("empty")

    def test_load_missing_run_function(self, loops_dir):
        loop_dir = loops_dir / "bad"
        loop_dir.mkdir(parents=True)
        (loop_dir / "workflow.py").write_text("meta = {'name': 'bad'}\n# no run()")
        from loopflow.discovery import load_loop
        with pytest.raises(SystemExit):
            load_loop("bad")


class TestListAgents:
    def test_list_agents(self, loops_dir):
        _create_loop(loops_dir, "hello", {"name": "hello", "description": "Test"},
                     agents=[
                         {"name": "reviewer", "description": "Code reviewer"},
                         {"name": "merger", "description": "Merge decision maker"},
                     ])
        from loopflow.discovery import list_agents
        agents = list_agents("hello")
        assert len(agents) == 2
        assert agents[0]["name"] == "merger"
        assert agents[1]["name"] == "reviewer"

    def test_list_agents_empty(self, loops_dir):
        _create_loop(loops_dir, "hello", {"name": "hello", "description": "Test"})
        from loopflow.discovery import list_agents
        agents = list_agents("hello")
        assert agents == []


class TestMetaPhases:
    """A1: meta.phases validation."""

    def test_meta_without_phases(self, loops_dir):
        """meta without phases field is valid."""
        _create_loop(loops_dir, "hello", {"name": "hello", "description": "Test"})
        from loopflow.discovery import load_loop
        mod, meta, _ = load_loop("hello")
        assert meta["name"] == "hello"
        assert "phases" not in meta

    def test_meta_with_valid_phases(self, loops_dir):
        """meta with valid phases list is accepted."""
        meta = {
            "name": "hello",
            "description": "Test",
            "phases": [
                {"title": "Research", "detail": "Collect info"},
                {"title": "Translate", "detail": "Translate results"},
            ],
        }
        _create_loop(loops_dir, "hello", meta)
        from loopflow.discovery import load_loop
        mod, loaded_meta, _ = load_loop("hello")
        assert loaded_meta["phases"] == meta["phases"]

    def test_meta_phases_not_list(self, loops_dir):
        """phases must be a list."""
        meta = {"name": "hello", "description": "Test", "phases": "not-a-list"}
        _create_loop(loops_dir, "hello", meta)
        from loopflow.discovery import load_loop
        with pytest.raises(SystemExit):
            load_loop("hello")

    def test_meta_phases_missing_title(self, loops_dir):
        """Each phase entry must have a title."""
        meta = {
            "name": "hello",
            "description": "Test",
            "phases": [{"detail": "no title here"}],
        }
        _create_loop(loops_dir, "hello", meta)
        from loopflow.discovery import load_loop
        with pytest.raises(SystemExit):
            load_loop("hello")

    def test_meta_phases_empty_list(self, loops_dir):
        """Empty phases list is valid."""
        meta = {"name": "hello", "description": "Test", "phases": []}
        _create_loop(loops_dir, "hello", meta)
        from loopflow.discovery import load_loop
        mod, loaded_meta, _ = load_loop("hello")
        assert loaded_meta["phases"] == []