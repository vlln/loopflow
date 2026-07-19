import subprocess

import pytest

from loopflow.infrastructure.web_resources import (
    BackendRepository,
    DiagnosticStartFailed,
    FileNotPreviewable,
    LoopRepository,
    PathForbidden,
    QueueRepository,
)


def make_loop(root, name="demo"):
    loop = root / name
    (loop / "agents").mkdir(parents=True)
    (loop / "loop.md").write_text("---\nname: demo\ndescription: Demo\n---\n# Demo\n")
    (loop / "workflow.py").write_text("def run():\n    pass\n")
    return loop


def test_loop_invalid_sibling_and_empty_agents(tmp_path):
    valid = make_loop(tmp_path, "valid")
    invalid = tmp_path / "invalid"
    invalid.mkdir()
    (invalid / "loop.md").write_text("---\n: broken\n---\n")
    repository = LoopRepository(tmp_path)

    items = {item["name"]: item for item in repository.list()}

    assert items["valid"]["valid"] is True
    assert items["invalid"]["valid"] is False
    assert repository.detail(valid)["agents"] == []


def test_loop_detail_includes_agent_files_and_recent_related_runs(tmp_path):
    from loopflow.infrastructure.web_storage import RunRepository
    from tests.web_support.factories import WebFixtureFactory

    factory = WebFixtureFactory(tmp_path)
    loop = factory.create_loop("demo")
    (loop / "agents" / "reviewer.md").write_text("---\nname: reviewer\ndescription: Reviews\n---\nPrompt\n")
    factory.create_run("related", loop="demo")
    factory.create_run("other", loop="other")
    repository = LoopRepository(factory.loops, RunRepository(factory.runs))

    detail = repository.detail(loop)

    assert detail["agents"][0]["name"] == "reviewer"
    assert [run["run_id"] for run in detail["runs"]] == ["related"]
    assert any(item["path"] == "loop.md" and item["previewable"] for item in detail["files"])


def test_loop_preview_rejects_traversal_symlink_binary_and_large(tmp_path):
    loop = make_loop(tmp_path)
    outside = tmp_path / "secret.txt"
    outside.write_text("secret")
    (loop / "escape").symlink_to(outside)
    (loop / "binary.bin").write_bytes(b"a\x00b")
    (loop / "large.txt").write_bytes(b"x" * (1024 * 1024 + 1))
    repository = LoopRepository(tmp_path)

    with pytest.raises(PathForbidden):
        repository.preview(loop, "../../secret.txt")
    with pytest.raises(PathForbidden):
        repository.preview(loop, "escape")
    with pytest.raises(FileNotPreviewable):
        repository.preview(loop, "binary.bin")
    with pytest.raises(FileNotPreviewable):
        repository.preview(loop, "large.txt")
    assert repository.preview(loop, "workflow.py")["read_only"] is True


def test_queue_projection_and_blocked_resources(tmp_path):
    repository = QueueRepository(tmp_path, lambda name: name != "gpu")
    item = repository.enqueue("demo", {}, {"repo": "/tmp/repo", "gpu": "1"}, 5)

    assert item["blocked_resources"] == ["gpu"]
    assert repository.list()[0]["task_id"] == item["task_id"]


def test_backend_diagnostic_redacts_and_decodes_invalid_utf8():
    def runner(*_args, **_kwargs):
        return subprocess.CompletedProcess([], 1, b"output: bad\xff\n", b"token=lf-secret-123; failed")

    result = BackendRepository(runner).diagnose("kimi", 100)

    assert "lf-secret-123" not in result["stderr"]
    assert result["stderr"] == "token=[REDACTED]; failed"
    assert "\ufffd" in result["stdout"]


def test_backend_timeout_unknown_and_start_failure():
    def timeout(*_args, **_kwargs):
        raise subprocess.TimeoutExpired("kimi", 0.1)

    assert BackendRepository(timeout).diagnose("kimi", 100)["reason"] == "timeout"
    with pytest.raises(KeyError):
        BackendRepository(timeout).diagnose("missing", 100)

    def fail(*_args, **_kwargs):
        raise OSError("cannot start")

    with pytest.raises(DiagnosticStartFailed):
        BackendRepository(fail).diagnose("kimi", 100)


def test_backend_list_reports_missing_and_unknown_version(monkeypatch):
    monkeypatch.setattr("loopflow.infrastructure.web_resources.shutil.which", lambda _binary: None)
    items = BackendRepository().list()
    assert items and all(item["status"] == "missing" for item in items)
    assert all(item["version"] is None for item in items)
