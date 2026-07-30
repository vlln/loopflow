import json
import subprocess

import pytest

from loopflow.infrastructure.web_resources import (
    BackendRepository,
    DiagnosticStartFailed,
    FileNotPreviewable,
    LoopRepository,
    PathForbidden,
    PREVIEW_LIMIT,
    QueueRepository,
    RAW_LIMIT,
    _extract_declared_args,
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


def test_ac035_declared_args_preserve_default_presence():
    result = _extract_declared_args({
        "args": [
            {"name": "missing"},
            {"name": "null", "default": None},
            {"name": "zero", "default": 0},
        ]
    })

    assert "default" not in result[0]
    assert result[1]["default"] is None
    assert result[2]["default"] == 0


def test_ac035_declared_args_skip_non_json_yaml_defaults(tmp_path):
    repository = LoopRepository(tmp_path)
    loop = make_loop(tmp_path, "dated")
    (loop / "loop.md").write_text(
        "---\nname: dated\nargs:\n"
        "  - name: released\n    default: 2026-07-29\n"
        "  - name: valid\n    default: 0\n---\n"
    )

    assert repository.summary(loop)["declared_args"] == [{
        "name": "valid", "default": 0, "description": "", "required": False,
    }]


def test_ac035_loop_md_top_level_args_and_legacy_workflow_fallback(tmp_path):
    repository = LoopRepository(tmp_path)
    declared = make_loop(tmp_path, "declared")
    (declared / "loop.md").write_text(
        "---\nname: declared\ndescription: Demo\nargs:\n  - name: topic\n    default: rna\n---\n"
    )
    (declared / "workflow.py").write_text(
        "meta = {'args': [{'name': 'wrong', 'default': 1}]}\ndef run(): pass\n"
    )
    invalid = make_loop(tmp_path, "invalid")
    (invalid / "loop.md").write_text(
        "---\nname: invalid\ndescription: Demo\nargs: nope\n---\n"
    )
    (invalid / "workflow.py").write_text(
        "meta = {'args': [{'name': 'wrong', 'default': 1}]}\ndef run(): pass\n"
    )
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "workflow.py").write_text(
        "meta = {'description': 'Legacy', 'args': [{'name': 'count', 'default': 2}]}\n"
        "def run(): pass\n"
    )

    assert repository.summary(declared)["declared_args"] == [
        {"name": "topic", "default": "rna", "description": "", "required": False}
    ]
    assert repository.summary(invalid)["declared_args"] == []
    assert repository.summary(legacy)["declared_args"] == [
        {"name": "count", "default": 2, "description": "", "required": False}
    ]


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


def test_ac033_loop_preview_binary_image_and_pdf_use_fixed_media_types(tmp_path, monkeypatch):
    loop = make_loop(tmp_path)
    expected_types = {
        "chart.png": "image/png",
        "photo.jpg": "image/jpeg",
        "photo.jpeg": "image/jpeg",
        "animation.gif": "image/gif",
        "figure.svg": "image/svg+xml",
        "image.webp": "image/webp",
        "bitmap.bmp": "image/bmp",
        "favicon.ico": "image/x-icon",
        "report.pdf": "application/pdf",
    }
    for name in expected_types:
        (loop / name).write_bytes(b"fixture")
    monkeypatch.setattr(
        "loopflow.infrastructure.web_resources.mimetypes.guess_type",
        lambda _name: ("application/x-platform-dependent", None),
    )
    repository = LoopRepository(tmp_path)

    for name, expected_type in expected_types.items():
        result = repository.preview(loop, name)
        assert result["encoding"] == "raw"
        assert result["content"] is None
        assert result["media_type"] == expected_type
        assert result["read_only"] is True

    raw_bytes, raw_type = repository.serve_raw(loop, "chart.png")
    assert raw_type == "image/png"
    assert raw_bytes == b"fixture"


def test_ac033_loop_preview_binary_rejects_oversized(tmp_path):
    loop = make_loop(tmp_path)
    (loop / "huge.png").write_bytes(b"\x89PNG" + b"\x00" * (50 * 1024 * 1024 + 1))
    repository = LoopRepository(tmp_path)

    with pytest.raises(FileNotPreviewable, match="binary preview limit"):
        repository.preview(loop, "huge.png")
    with pytest.raises(FileNotPreviewable, match="binary preview limit"):
        repository.serve_raw(loop, "huge.png")


def test_ac033_loop_preview_accepts_exact_text_and_raw_limits(tmp_path):
    loop = make_loop(tmp_path)
    (loop / "exact.txt").write_bytes(b"x" * PREVIEW_LIMIT)
    exact_raw = loop / "exact.png"
    with exact_raw.open("wb") as stream:
        stream.seek(RAW_LIMIT - 1)
        stream.write(b"x")
    repository = LoopRepository(tmp_path)

    assert repository.preview(loop, "exact.txt")["size"] == PREVIEW_LIMIT
    raw, media_type = repository.serve_raw(loop, "exact.png")
    assert len(raw) == RAW_LIMIT
    assert media_type == "image/png"


def test_ac033_loop_raw_rejects_non_whitelisted_extension(tmp_path):
    loop = make_loop(tmp_path)
    (loop / "payload.bin").write_bytes(b"binary")
    repository = LoopRepository(tmp_path)

    with pytest.raises(FileNotPreviewable, match="file type"):
        repository.serve_raw(loop, "payload.bin")


def test_loop_file_summary_marks_binary_previewable(tmp_path):
    loop = make_loop(tmp_path)
    (loop / "chart.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    (loop / "binary.bin").write_bytes(b"a\x00b")
    repository = LoopRepository(tmp_path)

    png_summary = repository.file_summary(loop, loop / "chart.png")
    assert png_summary["previewable"] is True

    bin_summary = repository.file_summary(loop, loop / "binary.bin")
    assert bin_summary["previewable"] is False


def test_queue_projection_and_blocked_resources(tmp_path):
    repository = QueueRepository(tmp_path, lambda name: name != "gpu")
    item = repository.enqueue("demo", {}, {"repo": "/tmp/repo", "gpu": "1"}, 5)

    assert item["blocked_resources"] == ["gpu"]
    assert item["status"] == "pending"
    assert item["status_reason"] is None
    assert item["superseded_by"] is None
    assert repository.list()[0]["task_id"] == item["task_id"]


def test_queue_projection_passthroughs_status_fields(tmp_path):
    """ADR-0047 §5: 投影透传 status/status_reason/superseded_by，未知 status 回退 pending。"""
    repository = QueueRepository(tmp_path)
    (tmp_path / "a.json").write_text(json.dumps({
        "loop": "demo", "args": {}, "resources": {}, "priority": 5,
        "created": "2026-07-25T00:00:00Z",
        "status": "deferred", "status_reason": "repo locked",
    }))
    (tmp_path / "b.json").write_text(json.dumps({
        "loop": "demo", "args": {}, "resources": {}, "priority": 6,
        "created": "2026-07-25T00:01:00Z",
        "status": "superseded", "superseded_by": "a",
    }))
    (tmp_path / "c.json").write_text(json.dumps({
        "loop": "demo", "args": {}, "resources": {}, "priority": 7,
        "created": "2026-07-25T00:02:00Z", "status": "unknown_state",
    }))

    items = {item["task_id"]: item for item in repository.list()}
    assert items["a"]["status"] == "deferred"
    assert items["a"]["status_reason"] == "repo locked"
    assert items["a"]["superseded_by"] is None
    assert items["b"]["status"] == "superseded"
    assert items["b"]["superseded_by"] == "a"
    assert items["c"]["status"] == "pending"


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
    assert "grok" in {item["name"] for item in items}
    assert "gork" not in {item["name"] for item in items}


def test_backend_diagnostics_do_not_accept_gork_typo():
    with pytest.raises(KeyError):
        BackendRepository().diagnose("gork", 100)
