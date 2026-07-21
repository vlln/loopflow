#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
source_dir="$repo_dir/web/dist"
target_dir="$repo_dir/src/loopflow/presentation/web/static"

if [ ! -f "$source_dir/index.html" ]; then
  echo "web/dist/index.html is missing; run npm build first" >&2
  exit 1
fi

rm -rf "$target_dir"
mkdir -p "$target_dir"
cp -R "$source_dir/." "$target_dir/"
