#!/usr/bin/env python3
"""Approve join requests via VK API (gated by APPROVE_ALLOW)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.vk_client import VkApiError, VkClient  # noqa: E402
from scripts.vk_ip_refresh import OneExtraRefresh, call_recovering_ip  # noqa: E402


def approval_targets(decision: dict) -> list[dict]:
    raw = decision.get("to_approve", [])
    targets: list[dict] = []
    fallback_gid = 0
    groups = decision.get("groups") or []
    if len(groups) == 1:
        fallback_gid = int(groups[0].get("group_id") or 0)

    for item in raw:
        if isinstance(item, dict):
            targets.append(
                {
                    "group_id": int(item["group_id"]),
                    "user_id": int(item["user_id"]),
                }
            )
        else:
            if not fallback_gid:
                raise ValueError("legacy to_approve[] needs groups[0].group_id")
            targets.append({"group_id": fallback_gid, "user_id": int(item)})
    return targets


def append_ledger(entries: list[dict]) -> None:
    ledger_path = ROOT / "memory" / "approved-ledger.md"
    if not ledger_path.exists():
        ledger_path.write_text("# Approved join requests ledger\n\n", encoding="utf-8")

    lines = []
    for entry in entries:
        lines.append(
            f"- {entry['ts']} run={entry['run_id']} group_id={entry.get('group_id', '-')} "
            f"user_id={entry['user_id']} status={entry['status']}"
        )
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir

    decision_path = run_dir / "decision.json"
    if not decision_path.exists():
        print(f"ERROR missing {decision_path}")
        return 1

    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    targets = approval_targets(decision)

    approve_allow = os.environ.get("APPROVE_ALLOW", "no").strip().lower()
    dry_run = os.environ.get("DRY_RUN", "yes").strip().lower()

    results: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()

    if approve_allow != "yes" or dry_run == "yes":
        for target in targets:
            results.append(
                {
                    "group_id": target["group_id"],
                    "user_id": target["user_id"],
                    "status": "dry_run",
                    "ts": now,
                    "run_id": args.run_id,
                }
            )
        out_path = run_dir / "approve-results.json"
        out_path.write_text(
            json.dumps(
                {
                    "mode": "dry_run",
                    "approve_allow": approve_allow,
                    "dry_run": dry_run,
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"OK dry-run: would approve {len(targets)} users -> {out_path}")
        return 0

    base = VkClient.from_env()
    errors = 0
    extra = OneExtraRefresh()

    for target in targets:
        entry = {
            "group_id": target["group_id"],
            "user_id": target["user_id"],
            "ts": now,
            "run_id": args.run_id,
        }
        try:
            ok = call_recovering_ip(
                base,
                extra,
                lambda t=target: base.with_group(t["group_id"]).approve_request(t["user_id"]),
            )
            entry["status"] = "approved" if ok else "failed"
        except VkApiError as exc:
            entry["status"] = "error"
            entry["error_code"] = exc.code
            entry["error_message"] = exc.message
            errors += 1
        results.append(entry)

    out_path = run_dir / "approve-results.json"
    out_path.write_text(
        json.dumps({"mode": "live", "results": results}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    append_ledger([r for r in results if r.get("status") == "approved"])

    print(f"OK approved={sum(1 for r in results if r.get('status') == 'approved')} errors={errors}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
