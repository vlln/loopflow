#!/usr/bin/env python3
from __future__ import annotations

import http.client
import re
import threading
import time
from importlib.resources import files


def main() -> int:
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
