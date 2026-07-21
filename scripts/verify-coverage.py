#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys


def main(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    totals = data["totals"]
    expected = {
        "percent_covered": 100.0,
        "num_branches": 2,
        "covered_branches": 2,
        "missing_branches": 0,
    }
    errors = [f"{key}: expected {value}, got {totals.get(key)}" for key, value in expected.items() if totals.get(key) != value]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("coverage probe ok: 2/2 branches, 100% total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
