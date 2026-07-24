#!/usr/bin/env python3
"""Validate pipeline run artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


REQUIRED_FILES = [
    "context.json",
    "requests.json",
    "decision.json",
    "approve-results.json",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("-o", "--output", help="Write JSON report to file")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir

    checks: dict[str, str] = {}
    errors = 0

    for name in REQUIRED_FILES:
        path = run_dir / name
        if path.exists():
            checks[name] = "PASS"
        else:
            checks[name] = "FAIL"
            errors += 1

    approve_path = run_dir / "approve-results.json"
    approve_errors = 0
    if approve_path.exists():
        data = json.loads(approve_path.read_text(encoding="utf-8"))
        for result in data.get("results", []):
            if result.get("status") == "error":
                approve_errors += 1
        if approve_errors:
            checks["approve_api"] = "FAIL"
            errors += 1
        else:
            checks["approve_api"] = "PASS"

    report = {
        "status": "PASS" if errors == 0 else "FAIL",
        "checks": checks,
        "approve_errors": approve_errors,
    }

    if args.output:
        out = Path(args.output)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"OK report -> {out}")

    print(f"SUMMARY status={report['status']} errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
