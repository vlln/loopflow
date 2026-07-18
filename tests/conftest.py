# loopflow conftest — shared fixtures for all tests

import json
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_loopflow_home():
    """Create a temporary ~/.loopflow directory with queue/ and locks/ subdirs."""
    d = Path(tempfile.mkdtemp())
    for sub in ["queue", "locks", "runs", "loops"]:
        (d / sub).mkdir(parents=True)
    old = os.environ.get("LOOPFLOW_HOME")
    os.environ["LOOPFLOW_HOME"] = str(d)
    yield d
    if old:
        os.environ["LOOPFLOW_HOME"] = old
    else:
        del os.environ["LOOPFLOW_HOME"]


@pytest.fixture
def queue_dir(temp_loopflow_home):
    """Temporary queue directory."""
    return temp_loopflow_home / "queue"


@pytest.fixture
def locks_dir(temp_loopflow_home):
    """Temporary locks directory."""
    return temp_loopflow_home / "locks"


@pytest.fixture
def loops_dir():
    """Temporary loops directory (overrides LOOPFLOW_LOOPS_DIR)."""
    d = Path(tempfile.mkdtemp()) / "loops"
    d.mkdir(parents=True)
    old = os.environ.get("LOOPFLOW_LOOPS_DIR")
    os.environ["LOOPFLOW_LOOPS_DIR"] = str(d)
    yield d
    if old:
        os.environ["LOOPFLOW_LOOPS_DIR"] = old
    else:
        del os.environ["LOOPFLOW_LOOPS_DIR"]


def create_loop(loops_dir: Path, name: str, meta: dict = None,
                agents: list[dict] = None, loop_md: dict = None):
    """Create a valid loop directory with loop.md (mandatory)."""
    loop_dir = loops_dir / name
    loop_dir.mkdir(parents=True)

    # Write loop.md (mandatory)
    if loop_md is None:
        loop_md = {"name": name, "description": "Test loop"}
    import yaml as _yaml
    frontmatter = _yaml.dump(loop_md, allow_unicode=True, default_flow_style=False).strip()
    (loop_dir / "loop.md").write_text(f"---\n{frontmatter}\n---\n\n# {name}\n")

    # Write workflow.py
    if meta is None:
        meta = {"name": name, "description": "Test loop"}
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
            agent_content = f"""---
name: {a['name']}
description: {a['description']}
{env_str}{skills_str}---
{body}
"""
            (agents_dir / f"{a['name']}.md").write_text(agent_content)


def create_queue_entry(queue_dir: Path, loop: str, args: dict = None,
                       resources: dict = None, priority: int = 5):
    """Create a queue entry JSON file. Returns the file path."""
    import uuid
    entry = {
        "loop": loop,
        "args": args or {},
        "resources": resources or {},
        "priority": priority,
        "created": "2026-07-18T10:00:00Z",
    }
    path = queue_dir / f"{uuid.uuid4().hex}.json"
    path.write_text(json.dumps(entry, indent=2))
    return path