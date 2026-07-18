#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tests.web_support.ac_manifest import check_manifest, generate_manifest, read_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ac", type=Path, default=Path("docs/ac/0010-webui.md"))
    parser.add_argument("--manifest", type=Path, default=Path("tests/system/cases.json"))
    parser.add_argument("--allow-planned", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    if args.write:
        manifest = generate_manifest(args.ac)
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        manifest = read_manifest(args.manifest)

    errors = check_manifest(manifest, args.ac, allow_planned=args.allow_planned)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"AC manifest ok: {len(manifest['cases'])} scenarios")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
