#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
smoke_dir=$(mktemp -d "${TMPDIR:-/tmp}/loopflow-wheel-smoke.XXXXXX")
trap 'rm -rf "$smoke_dir"' EXIT HUP INT TERM

cd "$repo_dir/web"
npm run build
cd "$repo_dir"
./scripts/sync-web-assets.sh

uv build --wheel --out-dir "$smoke_dir/dist"
uv venv --python 3.10 "$smoke_dir/venv"
uv pip install --python "$smoke_dir/venv/bin/python" "$smoke_dir"/dist/*.whl
"$smoke_dir/venv/bin/python" scripts/verify-wheel-assets.py
