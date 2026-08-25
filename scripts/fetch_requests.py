#!/usr/bin/env python3
"""Fetch pending join requests from one or more VK groups."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.group_ids import parse_group_ids  # noqa: E402
from scripts.vk_client import VkClient  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--count", type=int, default=100)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    run_dir.mkdir(parents=True, exist_ok=True)

    group_ids = parse_group_ids()
    base = VkClient.from_env(group_id=group_ids[0])

    groups: list[dict] = []
    total = 0
    for gid in group_ids:
        user_ids = base.with_group(gid).get_requests(count=args.count)
        groups.append({"group_id": gid, "count": len(user_ids), "user_ids": user_ids})
        total += len(user_ids)
        print(f"OK group_id={gid} pending={len(user_ids)}")

    payload = {
        "group_ids": group_ids,
        "groups": groups,
        "count": total,
        "group_id": group_ids[0],
        "user_ids": groups[0]["user_ids"] if len(group_ids) == 1 else [],
    }

    out_path = run_dir / "requests.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"OK fetched {total} requests across {len(group_ids)} groups -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
