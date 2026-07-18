#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET


AC_ID = re.compile(r"\bAC-\d{3}-[NBEF]-\d+\b")
COMMIT = re.compile(r"\b[0-9a-f]{7,40}\b")


def frontmatter_status(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    match = re.search(r"^status:\s*(\S+)\s*$", text[4:end], re.MULTILINE)
    return match.group(1) if match else None


def section(text: str, heading: str) -> str:
    match = re.search(
        rf"^#{{1,6}}\s+{re.escape(heading)}\s*$\n(.*?)(?=^#{{1,6}}\s+|\Z)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    return match.group(1) if match else ""


def declared_acceptance(plan: Path) -> set[str]:
    content = section(plan.read_text(encoding="utf-8"), "Acceptance")
    return set(AC_ID.findall(content))


def report_results(report: Path) -> tuple[dict[str, str], list[str]]:
    results: dict[str, str] = {}
    errors: list[str] = []
    for line in report.read_text(encoding="utf-8").splitlines():
        ids = AC_ID.findall(line)
        if not ids:
            continue
        states = [state for state in ("PASS", "FAIL", "TODO") if f"[{state}]" in line]
        if not states:
            continue
        for ac_id in ids:
            if ac_id in results:
                errors.append(f"duplicate Report result: {ac_id}")
            results[ac_id] = states[0]
            if states[0] == "PASS" and not COMMIT.search(line):
                errors.append(f"{ac_id}: PASS line lacks commit evidence")
    return results, errors


def coverage_percent(path: Path) -> float:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "totals" in data and "percent_covered" in data["totals"]:
        return float(data["totals"]["percent_covered"])
    total = data.get("total", {})
    metrics = [total.get(name, {}).get("pct") for name in ("lines", "statements", "functions", "branches")]
    if all(isinstance(value, (int, float)) for value in metrics):
        return min(float(value) for value in metrics)
    raise ValueError(f"unsupported coverage format: {path}")


def junit_is_green(path: Path) -> bool:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    tests = sum(int(suite.attrib.get("tests", "0")) for suite in suites)
    failures = sum(int(suite.attrib.get("failures", "0")) for suite in suites)
    errors = sum(int(suite.attrib.get("errors", "0")) for suite in suites)
    return tests > 0 and failures == 0 and errors == 0


def known_manifest_ids(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {case["ac_id"] for case in data["cases"]}


def run(args: argparse.Namespace) -> list[str]:
    errors: list[str] = []
    if frontmatter_status(args.plan) != "done":
        errors.append("Plan status must be done")
    if frontmatter_status(args.report) != "complete":
        errors.append("Report status must be complete")
    if not re.search(r"\|\s*01\s*\|.*\|\s*done\s*\|", args.container_readme.read_text(encoding="utf-8")):
        errors.append("container README must mark unit 01 done")

    declared = declared_acceptance(args.plan)
    known = known_manifest_ids(args.manifest)
    if not declared:
        errors.append("Plan Acceptance section must declare at least one AC scenario")
    unknown = declared - known
    if unknown:
        errors.append(f"Plan declares unknown AC ids: {', '.join(sorted(unknown))}")

    results, result_errors = report_results(args.report)
    errors.extend(result_errors)
    if set(results) != declared:
        missing = declared - set(results)
        extra = set(results) - declared
        if missing:
            errors.append(f"Report missing declared AC ids: {', '.join(sorted(missing))}")
        if extra:
            errors.append(f"Report contains undeclared AC ids: {', '.join(sorted(extra))}")
    for ac_id in sorted(declared):
        if results.get(ac_id) != "PASS":
            errors.append(f"{ac_id}: result must be PASS")

    for item in args.coverage:
        path_text, separator, threshold_text = item.rpartition(":")
        if not separator:
            errors.append(f"invalid coverage argument: {item}")
            continue
        try:
            actual = coverage_percent(Path(path_text))
            threshold = float(threshold_text)
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            errors.append(f"cannot read coverage {path_text}: {exc}")
            continue
        if actual < threshold:
            errors.append(f"coverage {path_text} is {actual:.2f}, below {threshold:.2f}")

    for result_path in args.result:
        try:
            if not junit_is_green(result_path):
                errors.append(f"test result is not green: {result_path}")
        except (OSError, ET.ParseError, ValueError) as exc:
            errors.append(f"cannot read test result {result_path}: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--container-readme", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=Path("tests/system/cases.json"))
    parser.add_argument("--coverage", action="append", default=[])
    parser.add_argument("--result", type=Path, action="append", default=[])
    args = parser.parse_args()

    errors = run(args)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("submission gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
