#!/usr/bin/env python3
from __future__ import annotations

import re
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

    print(f"wheel assets ok: index.html + {len(asset_paths)} hashed assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
