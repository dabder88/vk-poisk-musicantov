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


def groups_from_requests(data: dict) -> list[dict]:
    raw_groups = data.get("groups")
    if isinstance(raw_groups, list) and raw_groups:
        result = []
        for item in raw_groups:
            gid = int(item["group_id"])
            user_ids = [int(x) for x in item.get("user_ids", [])]
            result.append({"group_id": gid, "user_ids": user_ids})
        return result

    gid = int(data.get("group_id") or 0)
    user_ids = [int(x) for x in data.get("user_ids", [])]
    if not gid:
        raise ValueError("requests.json has no group_id/groups")
    return [{"group_id": gid, "user_ids": user_ids}]


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
    groups = groups_from_requests(data)
    mode = load_policy_mode()

    if mode not in ("approve_all", "manual_only"):
        print(f"ERROR unknown policy mode: {mode}")
        return 1

    to_approve: list[dict] = []
    skipped: list[dict] = []
    per_group: list[dict] = []

    for group in groups:
        gid = group["group_id"]
        user_ids = group["user_ids"]
        approved_ids: list[int] = []
        skipped_here: list[dict] = []
        if mode == "approve_all":
            approved_ids = user_ids
            to_approve.extend({"group_id": gid, "user_id": uid} for uid in approved_ids)
        else:
            skipped_here = [
                {"group_id": gid, "user_id": uid, "reason": "manual_only policy"}
                for uid in user_ids
            ]
            skipped.extend(skipped_here)
        per_group.append(
            {
                "group_id": gid,
                "to_approve": approved_ids,
                "skipped": skipped_here,
            }
        )

    decision = {
        "policy_mode": mode,
        "groups": per_group,
        "to_approve": to_approve,
        "skipped": skipped,
        "summary": {
            "groups": len(groups),
            "total": sum(len(g["user_ids"]) for g in groups),
            "approve": len(to_approve),
            "skip": len(skipped),
        },
    }

    out_path = run_dir / "decision.json"
    out_path.write_text(json.dumps(decision, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"OK decision: groups={len(groups)} approve={len(to_approve)} "
        f"skip={len(skipped)} mode={mode} -> {out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
