#!/usr/bin/env python3
from __future__ import annotations

import http.client
import importlib.metadata
import re
import threading
from importlib.resources import files
from pathlib import Path

# BL-061: the 0.28.0 release shipped with pyproject.toml still at 0.27.1 — the
# wheel built fine but reported the wrong version. Gate on version consistency:
#   weak (always)   — wheel installs what pyproject declares
#   strong (RELEASE) — CHANGELOG top entry matches pyproject (no "only bumped
#                     the changelog" releases)
_REPO_ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    text = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not match:
        raise SystemExit("pyproject.toml has no [project] version")
    return match.group(1)


def _changelog_top_version() -> str | None:
    path = _REPO_ROOT / "CHANGELOG.md"
    if not path.is_file():
        return None
    match = re.search(r"^## \[([^\]]+)\]", path.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else None


def _is_release_stage() -> bool:
    readme = _REPO_ROOT / "docs" / "README.md"
    if not readme.is_file():
        return False
    return "`RELEASE`" in readme.read_text(encoding="utf-8")


def _check_version_consistency() -> None:
    expected = _pyproject_version()
    installed = importlib.metadata.version("loopflow")
    if installed != expected:
        raise SystemExit(
            f"version mismatch: wheel installs loopflow=={installed}, "
            f"pyproject declares {expected}"
        )
    if _is_release_stage():
        top = _changelog_top_version()
        if top != expected:
            raise SystemExit(
                f"RELEASE gate: CHANGELOG top entry [{top}] != pyproject version {expected}. "
                "Bump pyproject.toml (and uv.lock) before releasing."
            )


def main() -> int:
    _check_version_consistency()

    static = files("loopflow.presentation.web").joinpath("static")
    index = static.joinpath("index.html")
    if not index.is_file():
        raise SystemExit("wheel does not contain static/index.html")

    markup = index.read_text(encoding="utf-8")
    asset_paths = re.findall(r'(?:src|href)="(/assets/[^"]+)"', markup)
    if not asset_paths:
        raise SystemExit("index.html does not reference hashed assets")
    if not all(re.search(r"-[A-Za-z0-9_-]{6,}\.", path) for path in asset_paths):
        raise SystemExit("index.html contains an unhashed asset reference")

    missing = [path for path in asset_paths if not static.joinpath(path.lstrip("/")).is_file()]
    if missing:
        raise SystemExit(f"wheel is missing referenced assets: {missing}")

    # End-to-end smoke: `loopflow web` must serve the built UI, not just ship files.
    # Regression for the 0.27.0 defect where the wheel had no assets at all.
    from loopflow.presentation.web.server import create_server

    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        conn.request("GET", "/")
        response = conn.getresponse()
        body = response.read()
        conn.close()
        if response.status != 200 or b"<!doctype html>" not in body.lower():
            raise SystemExit(f"GET / failed: status={response.status}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

    print(f"wheel assets ok: index.html + {len(asset_paths)} hashed assets; web serves UI")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
