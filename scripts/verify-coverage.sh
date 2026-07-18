#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
probe_dir=$(mktemp -d "${TMPDIR:-/tmp}/loopflow-coverage-probe.XXXXXX")
trap 'rm -rf "$probe_dir"' EXIT HUP INT TERM

cd "$repo_dir"
uv run pytest tests/infrastructure/coverage_probe/test_known.py -q \
  --cov=tests.infrastructure.coverage_probe.known \
  --cov-branch \
  --cov-report="json:$probe_dir/coverage.json"
python3 scripts/verify-coverage.py "$probe_dir/coverage.json"
