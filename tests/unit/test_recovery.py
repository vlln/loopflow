import json

import pytest

from loopflow.infrastructure.recovery import (
    ReplayDiverged,
    append_cache_event,
    call_input_digest,
    parallel_call_id,
    read_call_segments,
    select_for_replay,
)


def _segment(path, call_id, digest, *, status="succeeded", exit_code=0, text="ok"):
    append_cache_event(
        path,
        {"type": "agent_start", "call_id": call_id, "input_digest": digest},
    )
    append_cache_event(path, {"type": "agent_message_chunk", "content": text})
    if status is not None:
        append_cache_event(
            path,
            {
                "type": "agent_done",
                "call_id": call_id,
                "status": status,
                "session_id": "sid-1",
                "exit_code": exit_code,
            },
        )


def test_call_digest_is_stable_and_tracks_workflow_and_prompt(tmp_path):
    loop = tmp_path / "loop"
    loop.mkdir()
    (loop / "workflow.py").write_text("def run(**kwargs): pass\n")
    values = dict(
        loop_dir=loop,
        prompt="review",
        schema={"type": "object"},
        backend="fake",
        model=None,
        agent_definition="reader",
        execution_options={"mock": None},
    )

    first = call_input_digest(**values)
    assert first == call_input_digest(**values)
    assert first != call_input_digest(**{**values, "prompt": "changed"})
    (loop / "workflow.py").write_text("def run(**kwargs): return 1\n")
    assert first != call_input_digest(**values)


def test_reader_keeps_lifecycle_segments_separate(tmp_path):
    path = tmp_path / "0001.jsonl"
    _segment(path, "0001", "sha256:same", status="failed", exit_code=1, text="old")
    _segment(path, "0001", "sha256:same", text="new")

    first, second = read_call_segments(path)
    assert first.text == "old" and not first.committed
    assert second.text == "new" and second.committed


def test_replay_requires_matching_digest_and_committed_latest_segment(tmp_path):
    path = tmp_path / "0001.jsonl"
    _segment(path, "0001", "sha256:old")

    assert select_for_replay(path, call_id="0001", input_digest="sha256:old").outcome == "hit"
    with pytest.raises(ReplayDiverged):
        select_for_replay(path, call_id="0001", input_digest="sha256:new")

    interrupted = tmp_path / "0002.jsonl"
    _segment(interrupted, "0002", "sha256:same", status=None)
    assert (
        select_for_replay(interrupted, call_id="0002", input_digest="sha256:same").outcome
        == "uncommitted"
    )


def test_corrupt_tail_is_uncommitted_and_legacy_success_is_unverified(tmp_path):
    corrupt = tmp_path / "0001.jsonl"
    _segment(corrupt, "0001", "sha256:same", status=None)
    with corrupt.open("a") as stream:
        stream.write('{"type":"agent_done"')
    assert select_for_replay(corrupt, call_id="0001", input_digest="sha256:same").outcome == "uncommitted"

    legacy = tmp_path / "0002.jsonl"
    legacy.write_text(
        json.dumps({"type": "agent_message", "content": "legacy"})
        + "\n"
        + json.dumps({"type": "agent_done", "exit_code": 0})
        + "\n"
    )
    selection = select_for_replay(legacy, call_id="0002", input_digest="sha256:new")
    assert selection.outcome == "legacy_hit" and selection.segment.text == "legacy"


def test_parallel_call_ids_are_position_based():
    assert [parallel_call_id(3, branch) for branch in (2, 0, 1)] == [
        "0003.0002.0001",
        "0003.0000.0001",
        "0003.0001.0001",
    ]
