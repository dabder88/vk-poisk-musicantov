#!/usr/bin/env python3
"""Fetch pending join requests from VK group."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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

    client = VkClient.from_env()
    user_ids = client.get_requests(count=args.count)

    payload = {
        "group_id": client.group_id,
        "count": len(user_ids),
        "user_ids": user_ids,
    }

    out_path = run_dir / "requests.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"OK fetched {len(user_ids)} requests -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
