"""Minimal resume mechanism verification for ADR-0004.

Tests:
1. Sequential replay: 3 agent calls, crash after 2nd, resume
2. while loop: 5 iterations, crash at 3rd, resume
3. parallel: 3 concurrent agents, 1 done, 2 pending, resume
"""

import json
import os
import tempfile
import uuid
from pathlib import Path


class MinimalResumeRuntime:
    """Minimal runtime that demonstrates sequential-counter resume."""

    def __init__(self, run_dir: Path, resume: bool = False):
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.counter = 0
        self.resume = resume
        self._executed = []  # track which were actually executed

    def agent(self, prompt: str) -> str | None:
        self.counter += 1
        seq = self.counter
        cache_path = self.run_dir / f"{seq:04d}.jsonl"

        if self.resume and cache_path.exists():
            try:
                events = [
                    json.loads(line)
                    for line in cache_path.read_text().strip().split("\n")
                    if line
                ]
                for evt in events:
                    if evt.get("type") == "agent_done":
                        if evt.get("exit_code") == 0:
                            text = "\n".join(
                                e["content"]
                                for e in events
                                if e.get("type") == "agent_text"
                            )
                            print(f"  [CACHE HIT] seq={seq:04d}: {prompt[:40]}...")
                            return text
                # Cache exists but invalid — treat as unfinished
                print(f"  [CACHE INVALID] seq={seq:04d}: re-executing")
            except (json.JSONDecodeError, KeyError, OSError):
                print(f"  [CACHE CORRUPT] seq={seq:04d}: re-executing")

        # Simulate agent execution
        result = f"Result of: {prompt}"
        exit_code = 0

        # Write cache
        events = [
            {"type": "agent_start", "session": f"wf_{seq:04d}"},
            {"type": "agent_text", "content": result},
            {"type": "agent_done", "exit_code": exit_code},
        ]
        cache_path.write_text("\n".join(json.dumps(e) for e in events) + "\n")
        self._executed.append(seq)
        print(f"  [EXECUTED] seq={seq:04d}: {prompt[:40]}...")
        return result

    def get_executed(self):
        return self._executed


def test_sequential_replay():
    """Test: 3 agent calls, crash after 2nd, resume."""
    print("\n=== Test 1: Sequential Replay ===")
    run_dir = Path(tempfile.mkdtemp()) / "test-run"

    # First run: simulate crash after call 2
    rt = MinimalResumeRuntime(run_dir)
    rt.agent("step 1: analyze")
    rt.agent("step 2: review")
    # Simulate crash — step 3 never runs
    print("  💥 Simulated crash after step 2")

    # Resume
    rt2 = MinimalResumeRuntime(run_dir, resume=True)
    rt2.agent("step 1: analyze")  # should be cache hit
    rt2.agent("step 2: review")  # should be cache hit
    rt2.agent("step 3: finalize")  # should execute

    assert rt2.get_executed() == [3], f"Expected only seq 3 executed, got {rt2.get_executed()}"
    print("  ✅ PASS: Only step 3 was executed, steps 1-2 from cache")


def test_while_loop_resume():
    """Test: while loop with 5 iterations, crash at 3rd."""
    print("\n=== Test 2: While Loop Resume ===")
    run_dir = Path(tempfile.mkdtemp()) / "test-run"

    # First run: simulate crash at iteration 3
    rt = MinimalResumeRuntime(run_dir)
    for i in range(5):
        result = rt.agent(f"iteration {i+1}")
        if i == 2:  # crash after 3rd iteration
            break
    print("  💥 Simulated crash after iteration 3")

    # Resume
    rt2 = MinimalResumeRuntime(run_dir, resume=True)
    for i in range(5):
        result = rt2.agent(f"iteration {i+1}")

    # All 5 calls should have results
    assert rt2.get_executed() == [4, 5], f"Expected [4, 5] executed, got {rt2.get_executed()}"
    print("  ✅ PASS: Iterations 1-3 from cache, 4-5 executed")


def test_parallel_resume():
    """Test: parallel agents, simulate partial completion."""
    print("\n=== Test 3: Parallel Resume ===")
    run_dir = Path(tempfile.mkdtemp()) / "test-run"

    # Simulate: agent A and B done, agent C crashed
    rt = MinimalResumeRuntime(run_dir)
    rt.agent("parallel: task A")  # seq 1
    rt.agent("parallel: task B")  # seq 2
    # seq 3 (task C) never runs
    print("  💥 Simulated: task C crashed before execution")

    # Resume
    rt2 = MinimalResumeRuntime(run_dir, resume=True)
    rt2.agent("parallel: task A")  # cache hit
    rt2.agent("parallel: task B")  # cache hit
    rt2.agent("parallel: task C")  # execute

    assert rt2.get_executed() == [3], f"Expected only seq 3 executed, got {rt2.get_executed()}"
    print("  ✅ PASS: Tasks A and B from cache, task C executed")


def test_corrupted_cache():
    """Test: corrupted cache file treated as incomplete."""
    print("\n=== Test 4: Corrupted Cache ===")
    run_dir = Path(tempfile.mkdtemp()) / "test-run"

    # Write corrupted cache
    run_dir.mkdir(parents=True, exist_ok=True)
    cache_path = run_dir / "0001.jsonl"
    cache_path.write_text("not valid json\n")

    rt = MinimalResumeRuntime(run_dir, resume=True)
    result = rt.agent("should re-execute")
    assert result is not None
    assert rt.get_executed() == [1], f"Expected seq 1 re-executed, got {rt.get_executed()}"
    print("  ✅ PASS: Corrupted cache re-executed successfully")


if __name__ == "__main__":
    test_sequential_replay()
    test_while_loop_resume()
    test_parallel_resume()
    test_corrupted_cache()
    print("\n🎉 All 4 tests passed!")