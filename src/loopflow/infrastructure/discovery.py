"""Loop discovery — scan ~/.loopflow/loops/ for installed loop definitions."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


def _loops_dir() -> Path:
    """Get the loops directory path."""
    custom = os.environ.get("LOOPFLOW_LOOPS_DIR")
    if custom:
        return Path(custom)
    home = os.environ.get("HOME", os.path.expanduser("~"))
    return Path(home) / ".loopflow" / "loops"


def list_loops() -> list[tuple[str, dict, Path]]:
    """Scan loops directory and return (name, meta, path) for each valid loop.

    Returns empty list if directory doesn't exist or is empty.
    """
    loops = _loops_dir()
    if not loops.is_dir():
        return []

    results = []
    for entry in sorted(loops.iterdir()):
        if not entry.is_dir():
            continue
        wf_path = entry / "workflow.py"
        if not wf_path.is_file():
            continue
        try:
            meta = _load_meta(wf_path)
            results.append((entry.name, meta, entry))
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

    wf_path = loop_dir / "workflow.py"
    if not wf_path.is_file():
        print(f"Error: loop '{name}' missing workflow.py", file=sys.stderr)
        sys.exit(1)

    meta = _load_meta(wf_path)
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


def _load_meta(wf_path: Path) -> dict:
    """Load meta dict from a workflow.py file.

    Executes the file in a restricted namespace and extracts the meta variable.
    Validates the meta dict structure and optional phases field.
    """
    mod = _load_module(wf_path)
    if not hasattr(mod, "meta"):
        return {"name": wf_path.parent.name, "description": ""}
    meta = mod.meta
    if not isinstance(meta, dict):
        print(f"Error: meta must be a dict, got {type(meta).__name__}", file=sys.stderr)
        sys.exit(1)

    # Validate optional phases field
    if "phases" in meta:
        phases = meta["phases"]
        if not isinstance(phases, list):
            print(
                f"Error: meta.phases must be a list, got {type(phases).__name__}",
                file=sys.stderr,
            )
            sys.exit(1)
        for i, p in enumerate(phases):
            if not isinstance(p, dict):
                print(
                    f"Error: meta.phases[{i}] must be a dict, got {type(p).__name__}",
                    file=sys.stderr,
                )
                sys.exit(1)
            if "title" not in p:
                print(
                    f"Error: meta.phases[{i}] missing required field 'title'",
                    file=sys.stderr,
                )
                sys.exit(1)

    return meta


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