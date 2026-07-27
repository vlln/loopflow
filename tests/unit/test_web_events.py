from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from loopflow.infrastructure.web_events import EventWriter, project_events, replay_v2


def test_projects_agent_graph_from_agent_start_events(tmp_path):
    writer = EventWriter()
    run = tmp_path / "run-1"
    writer.append(run, "agent_start", run_id="run-1", call_id="c1", payload={"label": "planner", "agent_def": "planner"})
    writer.append(run, "agent_done", run_id="run-1", call_id="c1", payload={"exit_code": 0})
    writer.append(run, "agent_start", run_id="run-1", call_id="c2", payload={"label": "researcher", "agent_def": "researcher"})
    writer.append(run, "agent_done", run_id="run-1", call_id="c2", payload={"exit_code": 0})

    result = project_events(run / "events.jsonl")

    assert result.agent_graph["current"] == "c2"
    assert len(result.agent_graph["nodes"]) == 2
    assert result.agent_graph["nodes"][0] == {"id": "c1", "label": "planner", "agent_def": "planner", "status": "done"}
    assert result.agent_graph["nodes"][1] == {"id": "c2", "label": "researcher", "agent_def": "researcher", "status": "done"}
    assert result.agent_graph["edges"] == [{"from": "c1", "to": "c2", "kind": "sequential"}]
    assert len(result.calls) == 2


def test_malformed_v2_is_not_treated_as_unattributed(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps({"version": 2, "event_id": 1, "type": "agent_start", "ts": "x", "run_id": "r", "payload": {}}) + "\n")

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
    assert events[1]["call_id"] == "0001" and events[1]["phase_id"] == "phase-1"
    assert flat == {"type": "agent_done", "exit_code": 0}
