#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tests.web_support import ac_manifest as web_manifest
from tests.recovery_support import manifest as recovery_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("web", "recovery"), default="web")
    parser.add_argument("--ac", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--allow-planned", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    profile = recovery_manifest if args.profile == "recovery" else web_manifest
    if args.ac is None:
        args.ac = Path(
            "docs/ac/0011-recovery-intervention.md"
            if args.profile == "recovery"
            else "docs/ac/0010-webui.md"
        )
    if args.manifest is None:
        args.manifest = Path(
            "tests/system/recovery_cases.json"
            if args.profile == "recovery"
            else "tests/system/cases.json"
        )

    if args.write:
        manifest = profile.generate_manifest(args.ac)
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        manifest = profile.read_manifest(args.manifest)

    errors = profile.check_manifest(manifest, args.ac, allow_planned=args.allow_planned)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"AC manifest ok: {len(manifest['cases'])} scenarios")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
