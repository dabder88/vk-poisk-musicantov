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
from scripts.vk_client import VkApiError, VkClient  # noqa: E402
from scripts.vk_ip_refresh import run_per_group_with_one_extra_refresh  # noqa: E402


def group_payload(gid: int, user_ids: list[int]) -> dict:
    return {"group_id": gid, "count": len(user_ids), "user_ids": user_ids}


def group_error_payload(gid: int, exc: VkApiError) -> dict:
    return {
        "group_id": gid,
        "count": 0,
        "user_ids": [],
        "error_code": exc.code,
        "error_message": exc.message,
    }


def fetch_groups(client: VkClient, group_ids: list[int], count: int) -> tuple[list[dict], int]:
    def fetch_one(bound: VkClient, gid: int) -> dict:
        user_ids = bound.with_group(gid).get_requests(count=count)
        print(f"OK group_id={gid} pending={len(user_ids)}")
        return group_payload(gid, user_ids)

    _client, latest = run_per_group_with_one_extra_refresh(client, group_ids, fetch_one)
    groups: list[dict] = []
    errors = 0
    for gid in group_ids:
        item = latest[gid]
        if isinstance(item, VkApiError):
            print(f"ERROR group_id={gid} getRequests code={item.code} msg={item.message}")
            groups.append(group_error_payload(gid, item))
            errors += 1
        else:
            groups.append(item)
    return groups, errors


def build_payload(group_ids: list[int], groups: list[dict]) -> dict:
    total = sum(int(g.get("count") or 0) for g in groups)
    errors = sum(1 for g in groups if g.get("error_code") is not None)
    return {
        "group_ids": group_ids,
        "groups": groups,
        "count": total,
        "group_id": group_ids[0],
        "user_ids": groups[0]["user_ids"] if len(group_ids) == 1 else [],
        "errors": errors,
        "partial": errors > 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--count", type=int, default=100)
    args = parser.parse_args()

    if args.count > 200:
        print("WARN VK getRequests count max is 200; using 200")
        args.count = 200
    if args.count < 1:
        print("ERROR --count must be 1..200")
        return 1

    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    run_dir.mkdir(parents=True, exist_ok=True)

    group_ids = parse_group_ids()
    base = VkClient.from_env(group_id=group_ids[0])
    groups, errors = fetch_groups(base, group_ids, args.count)
    payload = build_payload(group_ids, groups)

    out_path = run_dir / "requests.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"{'OK' if errors == 0 else 'WARN'} fetched {payload['count']} requests "
        f"across {len(group_ids)} groups errors={errors} -> {out_path}"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
