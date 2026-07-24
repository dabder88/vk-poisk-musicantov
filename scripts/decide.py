#!/usr/bin/env python3
"""Decide which join requests to approve based on policy."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "shared" / "approve-policy.md"


def load_policy_mode() -> str:
    """Read policy mode from approve-policy.md front matter or default."""
    if not POLICY_PATH.exists():
        return "approve_all"

    text = POLICY_PATH.read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("mode:"):
            return stripped.split(":", 1)[1].strip()
    return "approve_all"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir

    requests_path = run_dir / "requests.json"
    if not requests_path.exists():
        print(f"ERROR missing {requests_path}")
        return 1

    data = json.loads(requests_path.read_text(encoding="utf-8"))
    user_ids = [int(x) for x in data.get("user_ids", [])]
    mode = load_policy_mode()

    approved: list[int] = []
    skipped: list[dict] = []

    if mode == "approve_all":
        approved = user_ids
    elif mode == "manual_only":
        skipped = [{"user_id": uid, "reason": "manual_only policy"} for uid in user_ids]
    else:
        print(f"ERROR unknown policy mode: {mode}")
        return 1

    decision = {
        "policy_mode": mode,
        "to_approve": approved,
        "skipped": skipped,
        "summary": {
            "total": len(user_ids),
            "approve": len(approved),
            "skip": len(skipped),
        },
    }

    out_path = run_dir / "decision.json"
    out_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"OK decision: approve={len(approved)} skip={len(skipped)} mode={mode} -> {out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
