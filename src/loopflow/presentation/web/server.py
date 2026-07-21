"""Standard-library HTTP, SSE, and static server for the local WebUI."""

from __future__ import annotations

import importlib.resources
import ipaddress
import json
import mimetypes
import os
import re
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from typing import Any, Callable
from urllib.parse import parse_qs, unquote, urlsplit

from loopflow.application.execution import BackgroundRunExecutor
from loopflow.application.web import ApplicationError, WebApplication
from loopflow.infrastructure.backends.diagnostics import BACKEND_META
from loopflow.infrastructure.web_resources import (
    BackendRepository,
    DiagnosticStartFailed,
    FileNotPreviewable,
    LoopRepository,
    PathForbidden,
    QueueRepository,
)
from loopflow.infrastructure.web_storage import RunRepository

MAX_BODY = 1024 * 1024
API_PREFIX = "/api/v1"
ERROR_STATUS = {
    "invalid_json": 400,
    "path_forbidden": 403,
    "loop_not_found": 404,
    "run_not_found": 404,
    "file_not_found": 404,
    "backend_not_found": 404,
    "invalid_run_transition": 409,
    "run_not_stale": 409,
    "process_alive": 409,
    "legacy_events_not_streamable": 409,
    "process_gone": 410,
    "cursor_out_of_range": 410,
    "request_too_large": 413,
    "validation_failed": 422,
    "file_not_previewable": 422,
    "atomic_write_failed": 500,
    "internal_error": 500,
    "diagnostic_start_failed": 503,
}


def build_application() -> WebApplication:
    home = Path(os.environ.get("LOOPFLOW_HOME", Path.home() / ".loopflow"))
    runs_root = Path(os.environ.get("LOOPFLOW_RUNS_DIR", home / "runs"))
    loops_root = Path(os.environ.get("LOOPFLOW_LOOPS_DIR", home / "loops"))
    queue_root = Path(os.environ.get("LOOPFLOW_QUEUE_DIR", home / "queue"))
    runs = RunRepository(runs_root)
    return WebApplication(
        runs=runs,
        loops=LoopRepository(loops_root, runs),
        queue=QueueRepository(queue_root),
        backends=BackendRepository(),
        executor=BackgroundRunExecutor(runs_root),
        allowed_backends=set(BACKEND_META),
    )


def handler_for(
    application: WebApplication,
    *,
    poll_interval: float = 0.1,
    static_root: Any | None = None,
) -> type[BaseHTTPRequestHandler]:
    class WebHandler(BaseHTTPRequestHandler):
        app = application
        server_version = "loopflow-web/1"

        def do_GET(self) -> None:
            self._dispatch("GET")

        def do_POST(self) -> None:
            self._dispatch("POST")

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _dispatch(self, method: str) -> None:
            try:
                split = urlsplit(self.path)
                path = unquote(split.path)
                query = parse_qs(split.query, keep_blank_values=True)
                if not path.startswith(API_PREFIX):
                    if method != "GET":
                        self._error(404, "file_not_found", "Static resource was not found")
                    else:
                        self._static(path)
                    return
                relative = path[len(API_PREFIX):] or "/"
                self._api(method, relative, query)
            except ApplicationError as error:
                self._error(ERROR_STATUS.get(error.code, 500), error.code, error.message, error.details)
            except PathForbidden as error:
                self._error(403, "path_forbidden", str(error))
            except FileNotPreviewable as error:
                self._error(422, "file_not_previewable", str(error))
            except FileNotFoundError as error:
                self._error(404, "file_not_found", f"File '{error.args[0]}' was not found")
            except DiagnosticStartFailed as error:
                self._error(503, "diagnostic_start_failed", str(error))
            except (BrokenPipeError, ConnectionResetError):
                return
            except OSError as error:
                self._error(500, "atomic_write_failed", str(error))
            except Exception:
                self._error(500, "internal_error", "An internal error occurred")

        def _api(self, method: str, path: str, query: dict[str, list[str]]) -> None:
            if method == "GET" and path == "/runs":
                self._json(200, self.app.list_runs(statuses=query.get("status"), loop=_one(query, "loop"), q=_one(query, "q"), limit=_integer(query, "limit", 50), cursor=_one(query, "cursor")))
                return
            if method == "POST" and path == "/runs":
                item = self.app.create_run(self._body())
                self._json(201, item, {"Location": f"{API_PREFIX}/runs/{item['run_id']}"})
                return
            if method == "GET" and path == "/loops":
                self._json(200, self.app.list_loops(q=_one(query, "q"), limit=_integer(query, "limit", 50), cursor=_one(query, "cursor")))
                return
            if method == "GET" and path == "/queue":
                self._json(200, self.app.list_queue(limit=_integer(query, "limit", 50), cursor=_one(query, "cursor")))
                return
            if method == "POST" and path == "/queue":
                item = self.app.enqueue(self._body())
                self._json(201, item, {"Location": f"{API_PREFIX}/queue/{item['task_id']}"})
                return
            if method == "GET" and path == "/backends":
                self._json(200, self.app.list_backends())
                return

            match = re.fullmatch(r"/runs/([^/]+)(?:/(stop|resume|rerun|reconcile|events|legacy-events))?", path)
            if match:
                run_id, action = match.groups()
                if method == "GET" and action is None:
                    self._json(200, self.app.get_run(run_id))
                elif method == "POST" and action == "stop":
                    self._require_empty_body()
                    self._json(200, self.app.stop_run(run_id))
                elif method == "POST" and action == "resume":
                    self._json(200, self.app.resume_run(run_id, self._body(optional=True)))
                elif method == "POST" and action == "rerun":
                    self._require_empty_body()
                    item = self.app.rerun(run_id)
                    self._json(201, item, {"Location": f"{API_PREFIX}/runs/{item['run_id']}"})
                elif method == "POST" and action == "reconcile":
                    self._require_empty_body()
                    self._json(200, self.app.reconcile(run_id))
                elif method == "GET" and action == "legacy-events":
                    self._json(200, self.app.legacy_events(run_id))
                elif method == "GET" and action == "events":
                    self._events(run_id, _integer(query, "last_event_id", 0))
                else:
                    self._error(404, "run_not_found", "Run endpoint was not found")
                return

            match = re.fullmatch(r"/loops/([^/]+)(?:/file)?", path)
            if match and method == "GET":
                name = match.group(1)
                if path.endswith("/file"):
                    relative = _one(query, "path")
                    if relative is None:
                        raise ApplicationError("validation_failed", "path is required")
                    self._json(200, self.app.preview_loop_file(name, relative))
                else:
                    self._json(200, self.app.get_loop(name))
                return

            match = re.fullmatch(r"/backends/([^/]+)/diagnostics", path)
            if match and method == "POST":
                body = self._body()
                if set(body) - {"timeout_ms"}:
                    raise ApplicationError("validation_failed", "Unknown fields")
                timeout = body.get("timeout_ms", 5000)
                self._json(200, self.app.diagnose_backend(match.group(1), timeout))
                return
            self._error(404, "file_not_found", "Endpoint was not found")

        def _events(self, run_id: str, last_event_id: int) -> None:
            initial, maximum, terminal = self.app.replay_events(run_id, last_event_id)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            cursor = last_event_id
            try:
                pending = initial
                while True:
                    for event in pending:
                        cursor = event["event_id"]
                        self._sse("run_event", event, cursor)
                    if terminal:
                        self._sse("stream_end", {"last_event_id": cursor}, cursor)
                        return
                    time.sleep(poll_interval)
                    pending, maximum, terminal = self.app.replay_events(run_id, cursor)
            except (BrokenPipeError, ConnectionResetError):
                return
            except Exception:
                try:
                    self._sse("stream_error", {"code": "event_read_failed", "last_event_id": cursor})
                except (BrokenPipeError, ConnectionResetError):
                    pass

        def _sse(self, event: str, data: dict[str, Any], event_id: int | None = None) -> None:
            if event_id is not None:
                self.wfile.write(f"id: {event_id}\n".encode())
            self.wfile.write(f"event: {event}\n".encode())
            self.wfile.write(b"data: " + json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode() + b"\n\n")
            self.wfile.flush()

        def _body(self, optional: bool = False) -> dict[str, Any]:
            length_text = self.headers.get("Content-Length")
            if length_text is None:
                if optional:
                    return {}
                raise ApplicationError("validation_failed", "JSON request body is required")
            try:
                length = int(length_text)
            except ValueError as error:
                raise ApplicationError("validation_failed", "Content-Length is invalid") from error
            if length > MAX_BODY:
                self.rfile.read(min(length, MAX_BODY + 1))
                raise ApplicationError("request_too_large", "Request body exceeds 1 MiB")
            raw = self.rfile.read(length)
            if not raw and optional:
                return {}
            try:
                body = json.loads(raw)
            except (json.JSONDecodeError, UnicodeDecodeError) as error:
                raise ApplicationError("invalid_json", "Request body is not valid JSON") from error
            if not isinstance(body, dict):
                raise ApplicationError("validation_failed", "Request body must be an object")
            return body

        def _require_empty_body(self) -> None:
            if int(self.headers.get("Content-Length", "0") or "0") != 0:
                raise ApplicationError("validation_failed", "Request body is not allowed")

        def _json(self, status: int, value: Any, headers: dict[str, str] | None = None) -> None:
            encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(encoded)

        def _error(self, status: int, code: str, message: str, details: dict[str, Any] | None = None) -> None:
            self._json(status, {"error": {"code": code, "message": message, "details": details or {}}})

        def _static(self, path: str) -> None:
            relative = path.lstrip("/") or "index.html"
            pure = PurePosixPath(relative)
            if pure.is_absolute() or ".." in pure.parts or not (relative == "index.html" or relative.startswith("assets/")):
                self._error(404, "file_not_found", "Static resource was not found")
                return
            root = static_root or importlib.resources.files("loopflow.presentation.web").joinpath("static")
            resource = root.joinpath(*pure.parts)
            if not resource.is_file():
                if "." not in pure.name:
                    resource = root.joinpath("index.html")
                else:
                    self._error(404, "file_not_found", "Static resource was not found")
                    return
            content = resource.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(resource.name)[0] or "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

    return WebHandler


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    allow_remote: bool = False,
    application: WebApplication | None = None,
    static_root: Any | None = None,
) -> ThreadingHTTPServer:
    if not is_loopback(host) and not allow_remote:
        raise ValueError("remote_bind_requires_allow_remote")
    return ThreadingHTTPServer(
        (host, port),
        handler_for(application or build_application(), static_root=static_root),
    )


def is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _one(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    if len(values) != 1:
        raise ApplicationError("validation_failed", f"{key} must be provided once")
    return values[0]


def _integer(query: dict[str, list[str]], key: str, default: int) -> int:
    value = _one(query, key)
    if value is None:
        return default
    try:
        result = int(value)
    except ValueError as error:
        raise ApplicationError("validation_failed", f"{key} must be an integer") from error
    if result < 0:
        raise ApplicationError("validation_failed", f"{key} must be non-negative")
    return result
