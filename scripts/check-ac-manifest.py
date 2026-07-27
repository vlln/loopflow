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
from tests.scheduling_support import manifest as scheduling_manifest
from tests.agent_support import manifest as agent_manifest

PROFILES = {
    "web": (web_manifest, "docs/ac/0010-webui.md", "tests/system/cases.json"),
    "recovery": (
        recovery_manifest,
        "docs/ac/0011-recovery-intervention.md",
        "tests/system/recovery_cases.json",
    ),
    "scheduling": (
        scheduling_manifest,
        "docs/ac/0004-scheduling.md",
        "tests/system/scheduling_cases.json",
    ),
    "agent": (
        agent_manifest,
        "docs/ac/0003-agent-layer.md",
        "tests/system/agent_cases.json",
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=tuple(PROFILES), default="web")
    parser.add_argument("--ac", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--allow-planned", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    profile, default_ac, default_manifest = PROFILES[args.profile]
    if args.ac is None:
        args.ac = Path(default_ac)
    if args.manifest is None:
        args.manifest = Path(default_manifest)

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
