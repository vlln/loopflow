"""Tests for loop discovery per AC-007 and AC-010."""

import tempfile
from pathlib import Path

import pytest

from tests.conftest import create_loop


@pytest.fixture
def loops_dir():
    d = Path(tempfile.mkdtemp()) / "loops"
    d.mkdir(parents=True)
    old = None
    import os
    old = os.environ.get("LOOPFLOW_LOOPS_DIR")
    os.environ["LOOPFLOW_LOOPS_DIR"] = str(d)
    yield d
    if old:
        os.environ["LOOPFLOW_LOOPS_DIR"] = old
    else:
        del os.environ["LOOPFLOW_LOOPS_DIR"]


class TestListLoops:
    def test_empty_directory(self, loops_dir):
        from loopflow.infrastructure.discovery import list_loops
        result = list_loops()
        assert result == []

    def test_single_loop(self, loops_dir):
        create_loop(loops_dir, "hello")
        from loopflow.infrastructure.discovery import list_loops
        result = list_loops()
        assert len(result) == 1
        assert result[0][0] == "hello"
        assert result[0][1]["name"] == "hello"

    def test_multiple_loops(self, loops_dir):
        create_loop(loops_dir, "loop-a")
        create_loop(loops_dir, "loop-b")
        from loopflow.infrastructure.discovery import list_loops
        result = list_loops()
        assert len(result) == 2

    def test_no_loop_md_not_discoverable(self, loops_dir):
        """Loop without loop.md is not discoverable."""
        loop_dir = loops_dir / "hidden"
        loop_dir.mkdir(parents=True)
        (loop_dir / "workflow.py").write_text("""
meta = {"name": "hidden", "description": "No loop.md"}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    return agent("hello")
""")
        from loopflow.infrastructure.discovery import list_loops
        result = list_loops()
        assert result == []


class TestLoadLoop:
    def test_load_valid_loop(self, loops_dir):
        create_loop(loops_dir, "hello")
        from loopflow.infrastructure.discovery import load_loop
        mod, meta, loop_dir = load_loop("hello")
        assert meta["name"] == "hello"
        assert hasattr(mod, "run")
        assert loop_dir.is_dir()

    def test_load_missing_workflow(self, loops_dir):
        loop_dir = loops_dir / "empty"
        loop_dir.mkdir(parents=True)
        (loop_dir / "loop.md").write_text("---\nname: empty\ndescription: Test\n---\n# empty\n")
        from loopflow.infrastructure.discovery import load_loop
        with pytest.raises(SystemExit):
            load_loop("empty")

    def test_load_missing_loop_md(self, loops_dir):
        """Loop without loop.md cannot be loaded."""
        loop_dir = loops_dir / "bad"
        loop_dir.mkdir(parents=True)
        (loop_dir / "workflow.py").write_text("""
meta = {"name": "bad", "description": "No loop.md"}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    return agent("hello")
""")
        from loopflow.infrastructure.discovery import load_loop
        with pytest.raises(SystemExit):
            load_loop("bad")

    def test_load_missing_run_function(self, loops_dir):
        loop_dir = loops_dir / "bad"
        loop_dir.mkdir(parents=True)
        (loop_dir / "loop.md").write_text("---\nname: bad\ndescription: No run()\n---\n# bad\n")
        (loop_dir / "workflow.py").write_text("meta = {'name': 'bad'}\n# no run()")
        from loopflow.infrastructure.discovery import load_loop
        with pytest.raises(SystemExit):
            load_loop("bad")


class TestListAgents:
    def test_list_agents(self, loops_dir):
        create_loop(loops_dir, "hello",
                    agents=[
                        {"name": "reviewer", "description": "Code reviewer"},
                        {"name": "merger", "description": "Merge decision maker"},
                    ])
        from loopflow.infrastructure.discovery import list_agents
        agents = list_agents("hello")
        assert len(agents) == 2
        assert agents[0]["name"] == "merger"
        assert agents[1]["name"] == "reviewer"

    def test_list_agents_empty(self, loops_dir):
        create_loop(loops_dir, "hello")
        from loopflow.infrastructure.discovery import list_agents
        agents = list_agents("hello")
        assert agents == []


class TestLoopMd:
    """AC-010: loop.md discovery."""

    def test_loop_md_with_triggers(self, loops_dir):
        create_loop(loops_dir, "fix-issue",
                    loop_md={
                        "name": "fix-issue",
                        "description": "Fix issues",
                        "triggers": [
                            {"type": "manual"},
                            {"type": "cron", "schedule": "*/5 * * * *"},
                        ],
                        "resources": [
                            {"type": "repo"},
                        ],
                    })
        from loopflow.infrastructure.discovery import list_loops
        result = list_loops()
        assert len(result) == 1
        meta = result[0][1]
        assert meta["name"] == "fix-issue"
        assert len(meta["triggers"]) == 2
        assert meta["triggers"][0]["type"] == "manual"
        assert meta["triggers"][1]["type"] == "cron"

    def test_loop_md_missing_name(self, loops_dir):
        """loop.md without name field is rejected."""
        loop_dir = loops_dir / "bad"
        loop_dir.mkdir(parents=True)
        (loop_dir / "loop.md").write_text("---\ndescription: No name\n---\n# bad\n")
        (loop_dir / "workflow.py").write_text("""
meta = {"name": "bad", "description": "Test"}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    return agent("hello")
""")
        from loopflow.infrastructure.discovery import list_loops
        result = list_loops()
        assert result == []

    def test_loop_md_bad_yaml(self, loops_dir):
        """Corrupt loop.md YAML is skipped."""
        loop_dir = loops_dir / "broken"
        loop_dir.mkdir(parents=True)
        (loop_dir / "loop.md").write_text("---\ninvalid: [\n---\n# broken")
        (loop_dir / "workflow.py").write_text("""
meta = {"name": "broken", "description": "Test"}

def run(agent, parallel, pipeline, phase, log, args, workflow):
    return agent("hello")
""")
        from loopflow.infrastructure.discovery import list_loops
        result = list_loops()
        assert result == []