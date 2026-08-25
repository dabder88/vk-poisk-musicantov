#!/usr/bin/env python3
"""Initialize a pipeline run directory."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.group_ids import parse_group_ids  # noqa: E402

RUNS_DIR = ROOT / "memory" / "runs"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    run_dir = RUNS_DIR / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        group_ids = parse_group_ids()
    except ValueError:
        group_ids = []

    context = {
        "run_id": args.run_id,
        "run_dir": str(run_dir.relative_to(ROOT)),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "started",
        "group_ids": group_ids,
    }

    context_path = run_dir / "context.json"
    context_path.write_text(json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"OK run initialized: {context_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
