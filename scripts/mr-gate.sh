#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
artifact_dir=${LOOPFLOW_GATE_ARTIFACTS:-"$repo_dir/.artifacts/mr-gate"}
mkdir -p "$artifact_dir"
export NO_PROXY="127.0.0.1,localhost${NO_PROXY:+,$NO_PROXY}"
export no_proxy="127.0.0.1,localhost${no_proxy:+,$no_proxy}"

cd "$repo_dir"
uv run pytest tests/ -q \
  --cov=src/loopflow \
  --cov-report=term \
  --cov-report="json:$artifact_dir/python-coverage.json" \
  --cov-report="xml:$artifact_dir/python-coverage.xml" \
  --junitxml="$artifact_dir/python-junit.xml"

if grep -Fq '| **当前阶段** | `TEST_INFRA` |' docs/README.md; then
  python3 scripts/check-ac-manifest.py --allow-planned
else
  python3 scripts/check-ac-manifest.py
fi

cd "$repo_dir/web"
npm ci
npm run typecheck
npm run test:coverage -- --reporter=default --reporter=junit --outputFile.junit="$artifact_dir/frontend-junit.xml"
npm run build
npm audit --audit-level=low
npm run test:browser

cd "$repo_dir"
./scripts/wheel-smoke.sh
