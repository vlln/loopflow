from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from loopflow.infrastructure.web_events import EventWriter, project_events, replay_v2


def test_projects_repeated_phase_occurrences_and_parallel_calls(tmp_path):
    writer = EventWriter()
    run = tmp_path / "run-1"
    for phase, phase_id, occurrence in (("Review", "p1", 1), ("Fix", "p2", 1), ("Review", "p3", 2)):
        writer.append(run, "phase", run_id="run-1", phase=phase, phase_id=phase_id, payload={"occurrence": occurrence})
    for call_id in ("c1", "c2"):
        writer.append(run, "agent_start", run_id="run-1", phase="Review", phase_id="p3", call_id=call_id, payload={"session": call_id})
        writer.append(run, "agent_done", run_id="run-1", phase="Review", phase_id="p3", call_id=call_id, payload={"exit_code": 0})

    result = project_events(run / "events.jsonl")

    assert result.graph["nodes"] == [
        {"phase": "Review", "occurrence_count": 2, "is_current": True},
        {"phase": "Fix", "occurrence_count": 1, "is_current": False},
    ]
    assert result.graph["edges"][-1] == {"from": "Fix", "to": "Review", "count": 1, "is_backedge": True}
    assert result.occurrences[-1]["call_ids"] == ["c1", "c2"]
    assert {call["call_id"] for call in result.calls} == {"c1", "c2"}


def test_malformed_v2_is_not_treated_as_unattributed(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps({"version": 2, "event_id": 1, "type": "agent_start", "ts": "x", "run_id": "r", "payload": {}, "call_id": "c"}) + "\n")

    result = project_events(path)

    assert len(result.malformed) == 1
    assert result.unattributed == []


def test_legacy_ambiguous_events_remain_unattributed(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text('\n'.join([json.dumps({"type": "phase", "title": "Review"}), json.dumps({"type": "agent_message", "content": "ambiguous"})]) + "\n")

    result = project_events(path)

    assert result.legacy is True
    assert result.unattributed == [{"type": "agent_message", "content": "ambiguous"}]


def test_incomplete_final_line_is_hidden_until_completed(tmp_path):
    path = tmp_path / "events.jsonl"
    first = {"version": 2, "event_id": 1, "type": "log", "ts": "x", "run_id": "r", "payload": {}}
    second = {"version": 2, "event_id": 2, "type": "log", "ts": "x", "run_id": "r", "payload": {}}
    encoded = json.dumps(second)
    path.write_text(json.dumps(first) + "\n" + encoded[:10])
    assert [event["event_id"] for event in project_events(path).events] == [1]
    with path.open("a") as stream:
        stream.write(encoded[10:] + "\n")
    assert [event["event_id"] for event in project_events(path).events] == [1, 2]


def test_writer_allocates_strictly_increasing_ids_under_threads(tmp_path):
    writer = EventWriter()
    run = tmp_path / "run"

    with ThreadPoolExecutor(max_workers=8) as pool:
        events = list(pool.map(lambda _: writer.append(run, "log", run_id="run", payload={}), range(50)))

    assert sorted(event["event_id"] for event in events) == list(range(1, 51))


def test_replay_rejects_legacy_and_out_of_range_cursor(tmp_path):
    writer = EventWriter()
    run = tmp_path / "run"
    writer.append(run, "log", run_id="run", payload={})
    writer.append(run, "log", run_id="run", payload={})
    assert [event["event_id"] for event in replay_v2(run / "events.jsonl", 1)[0]] == [2]
    with pytest.raises(IndexError) as error:
        replay_v2(run / "events.jsonl", 3)
    assert error.value.args == (2,)

    legacy = tmp_path / "legacy.jsonl"
    legacy.write_text('{"type":"log"}\n')
    with pytest.raises(ValueError, match="legacy_events_not_streamable"):
        replay_v2(legacy, 0)


def test_runtime_context_writes_v2_but_keeps_resume_cache_flat(tmp_path):
    from loopflow.infrastructure.context import RunContext, _append_cache, _write_event, set_context
    from loopflow.presentation.events import _emit_phase

    context = RunContext(run_id="run-1", run_dir=tmp_path)
    set_context(context)
    _emit_phase("Review")
    session = context.next_session()
    _write_event({"type": "agent_start", "session": session})
    cache = tmp_path / "0001.jsonl"
    _append_cache(cache, {"type": "agent_done", "exit_code": 0})

    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    flat = json.loads(cache.read_text())

    assert events[0]["phase"] == "Review" and events[0]["phase_id"] == "phase-1"
    assert events[1]["call_id"] == session and events[1]["phase_id"] == "phase-1"
    assert flat == {"type": "agent_done", "exit_code": 0}
