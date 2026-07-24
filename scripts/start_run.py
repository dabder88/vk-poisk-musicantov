#!/usr/bin/env python3
"""Initialize a pipeline run directory."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "memory" / "runs"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    run_dir = RUNS_DIR / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    context = {
        "run_id": args.run_id,
        "run_dir": str(run_dir.relative_to(ROOT)),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "started",
    }

    context_path = run_dir / "context.json"
    context_path.write_text(json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"OK run initialized: {context_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
