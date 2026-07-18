"""Loop discovery — scan ~/.loopflow/loops/ for installed loop definitions."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import yaml


def _loops_dir() -> Path:
    """Get the loops directory path."""
    custom = os.environ.get("LOOPFLOW_LOOPS_DIR")
    if custom:
        return Path(custom)
    home = os.environ.get("HOME", os.path.expanduser("~"))
    return Path(home) / ".loopflow" / "loops"


def _load_loop_meta(loop_dir: Path) -> dict:
    """Parse loop.md frontmatter. loop.md is mandatory.

    Raises SystemExit if loop.md is missing or invalid.
    """
    loop_md_path = loop_dir / "loop.md"
    if not loop_md_path.is_file():
        print(f"Error: {loop_dir.name} missing loop.md", file=sys.stderr)
        sys.exit(1)

    try:
        text = loop_md_path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            print(f"Error: {loop_md_path} missing frontmatter", file=sys.stderr)
            sys.exit(1)
        parts = text.split("---", 2)
        if len(parts) < 3:
            print(f"Error: {loop_md_path} invalid frontmatter", file=sys.stderr)
            sys.exit(1)
        frontmatter = yaml.safe_load(parts[1])
        if not isinstance(frontmatter, dict):
            print(f"Error: {loop_md_path} frontmatter must be a dict", file=sys.stderr)
            sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error: {loop_md_path} invalid YAML: {e}", file=sys.stderr)
        sys.exit(1)

    if "name" not in frontmatter:
        print(f"Error: {loop_md_path} missing required field 'name'", file=sys.stderr)
        sys.exit(1)

    return frontmatter


def list_loops() -> list[tuple[str, dict, Path]]:
    """Scan loops directory and return (name, meta, path) for each valid loop.

    Only loops with a valid loop.md are discoverable.
    Returns empty list if directory doesn't exist or is empty.
    """
    loops = _loops_dir()
    if not loops.is_dir():
        return []

    results = []
    for entry in sorted(loops.iterdir()):
        if not entry.is_dir():
            continue
        loop_md = entry / "loop.md"
        if not loop_md.is_file():
            continue
        wf_path = entry / "workflow.py"
        if not wf_path.is_file():
            continue
        try:
            meta = _load_loop_meta(entry)
            results.append((entry.name, meta, entry))
        except SystemExit:
            continue
        except Exception:
            continue

    return results


def load_loop(name: str):
    """Load a loop by name. Returns (module, meta, loop_dir).

    Raises SystemExit if loop not found or invalid.
    """
    loops = _loops_dir()
    loop_dir = loops / name
    if not loop_dir.is_dir():
        print(f"Error: loop '{name}' not found", file=sys.stderr)
        sys.exit(1)

    loop_md = loop_dir / "loop.md"
    if not loop_md.is_file():
        print(f"Error: loop '{name}' missing loop.md", file=sys.stderr)
        sys.exit(1)

    wf_path = loop_dir / "workflow.py"
    if not wf_path.is_file():
        print(f"Error: loop '{name}' missing workflow.py", file=sys.stderr)
        sys.exit(1)

    meta = _load_loop_meta(loop_dir)
    mod = _load_module(wf_path)

    if not hasattr(mod, "run"):
        print(f"Error: {wf_path} must define a run() function", file=sys.stderr)
        sys.exit(1)

    return mod, meta, loop_dir


def list_agents(loop_name: str) -> list[dict]:
    """List agent definitions for a loop."""
    loops = _loops_dir()
    agents_dir = loops / loop_name / "agents"
    if not agents_dir.is_dir():
        return []

    agents = []
    for entry in sorted(agents_dir.glob("*.md")):
        if entry.name.startswith("_"):
            continue  # skip abstract agents
        try:
            from loopflow.infrastructure.repository import parse_agent
            agent = parse_agent(entry)
            agents.append({
                "name": agent.name,
                "description": agent.description,
                "file": str(entry),
            })
        except Exception:
            continue

    return agents


def _load_module(wf_path: Path):
    """Load a Python module from a file path."""
    spec = importlib.util.spec_from_file_location(
        f"loop_{wf_path.parent.name}", wf_path
    )
    if spec is None or spec.loader is None:
        print(f"Error: cannot load {wf_path}", file=sys.stderr)
        sys.exit(1)

    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        print(f"Error: failed to load {wf_path}: {e}", file=sys.stderr)
        sys.exit(1)

    return mod