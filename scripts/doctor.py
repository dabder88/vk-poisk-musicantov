#!/usr/bin/env python3
"""Preflight checks for VK join-request pipeline."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.group_ids import parse_group_ids  # noqa: E402
from scripts.vk_client import VkClient  # noqa: E402


REQUIRED_DIRS = [
    "agents",
    ".cursor/agents",
    "skills",
    ".cursor/skills",
    "shared",
    "scripts",
    "memory",
    "memory/runs",
]

OPTIONAL_ENV = [
    "VK_GROUP_ID",
    "VK_GROUP_IDS",
    "VK_ACCESS_TOKEN",
    "VK_REFRESH_TOKEN",
    "VK_DEVICE_ID",
    "VK_CLIENT_ID",
    "VK_SERVICE_TOKEN",
    "VK_API_VERSION",
    "APPROVE_ALLOW",
    "DRY_RUN",
]


def main() -> int:
    errors = 0
    warnings = 0

    for rel in REQUIRED_DIRS:
        path = ROOT / rel
        if path.exists():
            print(f"OK path {rel}")
        else:
            print(f"ERROR missing path {rel}")
            errors += 1

    for name in OPTIONAL_ENV:
        value = os.environ.get(name, "").strip()
        if value:
            print(f"OK env {name} configured")
        else:
            print(f"WARN env {name} not set (using default)")
            warnings += 1

    try:
        group_ids = parse_group_ids()
        print(f"OK group_ids={','.join(str(x) for x in group_ids)}")
    except ValueError as exc:
        print(f"ERROR {exc}")
        errors += 1
        group_ids = []

    has_access = bool(os.environ.get("VK_ACCESS_TOKEN", "").strip())
    has_refresh = bool(os.environ.get("VK_REFRESH_TOKEN", "").strip())
    has_device = bool(os.environ.get("VK_DEVICE_ID", "").strip())

    if not has_access and not has_refresh:
        print("ERROR set VK_ACCESS_TOKEN or VK_REFRESH_TOKEN")
        errors += 1
    elif has_refresh and not has_device:
        print("ERROR VK_DEVICE_ID is required together with VK_REFRESH_TOKEN")
        errors += 1
    elif has_refresh:
        print(
            "OK will refresh access_token at most once on this host; "
            "later processes reuse gitignored memory/site.env.local"
        )
    else:
        print("WARN VK_REFRESH_TOKEN not set; Cloud Agent may hit error 5 (IP bind)")
        warnings += 1

    approve_allow = os.environ.get("APPROVE_ALLOW", "no").strip().lower()
    if approve_allow not in ("yes", "no"):
        print("ERROR APPROVE_ALLOW must be yes or no")
        errors += 1
    else:
        print(f"OK APPROVE_ALLOW={approve_allow}")

    if errors == 0:
        try:
            from scripts.vk_client import IP_RETRY_CODES
            from scripts.vk_oauth import refresh_from_env

            client = VkClient.from_env(group_id=group_ids[0])
            extra_refresh_done = False
            remaining = list(group_ids)
            while remaining:
                still_ip: list[int] = []
                for gid in remaining:
                    probe = client.with_group(gid).probe_token()
                    if probe["ok"]:
                        print(
                            f"OK VK API groups.getRequests reachable group_id={gid} "
                            f"sample={probe['pending_count_sample']}"
                        )
                        continue
                    code = probe.get("error_code")
                    msg = probe.get("error_message")
                    print(
                        f"ERROR VK API probe failed group_id={gid}: code={code} msg={msg}"
                    )
                    if code == 27:
                        print(
                            "HINT error 27: VK_ACCESS_TOKEN is a community (group) token. "
                            "groups.getRequests requires a USER token with groups scope. "
                            "See docs/how-to-get-vk-user-token.md"
                        )
                    elif code == 15:
                        print(
                            "HINT error 15: token lacks groups permission or user is not "
                            "group admin. See docs/how-to-get-vk-user-token.md"
                        )
                    elif code in IP_RETRY_CODES:
                        print(
                            "HINT error 5/1130 (IP): retried getRequests with the same "
                            "host-bound token. Second refresh only if cache empty or "
                            "retries still fail."
                        )
                        still_ip.append(gid)
                    errors += 1

                if still_ip and not extra_refresh_done:
                    print(
                        "WARN getRequests still error 5 after retries; "
                        "one extra refresh then re-probe (not a loop)"
                    )
                    extra_refresh_done = True
                    tokens = refresh_from_env(force=True)
                    client = client.with_group(group_ids[0])
                    client.access_token = str(tokens["access_token"]).strip()
                    errors -= len(still_ip)
                    remaining = still_ip
                    continue
                break
        except Exception as extra:  # noqa: BLE001
            print(f"ERROR VK client: {extra}")
            errors += 1

    if errors and not (
        os.environ.get("VK_ACCESS_TOKEN", "").strip()
        or os.environ.get("VK_REFRESH_TOKEN", "").strip()
    ):
        print(
            "HINT secrets not visible in this VM session. "
            "Restart Cloud Agent after adding Cursor Runtime Secrets, "
            "then run: bash scripts/run_pipeline.sh"
        )

    print(f"SUMMARY errors={errors} warnings={warnings}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
