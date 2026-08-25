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

# VK ID access_token prefix. Refresh tokens are typically vk2.r.
VK_ACCESS_TOKEN_PREFIX = "vk2.a."

HINT_REFRESH_TOKEN_IS_ACCESS = (
    "HINT VK_REFRESH_TOKEN is an access_token (prefix vk2.a.), not a refresh_token. "
    "Need a VK ID refresh_token (usually vk2.r.…). "
    "How to get: python3 scripts/get_vk_token.py start then finish --redirect-url ... "
    "Replace VK_REFRESH_TOKEN in Cursor Secrets; do not put vk2.a. into refresh."
)


def looks_like_vk_access_token(token: str) -> bool:
    """True if value looks like a VK ID access_token (vk2.a.), not refresh (vk2.r.)."""
    return token.strip().startswith(VK_ACCESS_TOKEN_PREFIX)


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
    refresh_token = os.environ.get("VK_REFRESH_TOKEN", "").strip()
    has_refresh = bool(refresh_token)
    has_device = bool(os.environ.get("VK_DEVICE_ID", "").strip())

    if not has_access and not has_refresh:
        print("ERROR set VK_ACCESS_TOKEN or VK_REFRESH_TOKEN")
        errors += 1
    elif has_refresh and looks_like_vk_access_token(refresh_token):
        print(
            "ERROR VK_REFRESH_TOKEN starts with vk2.a. — this is an access_token, "
            "not a refresh_token"
        )
        print(HINT_REFRESH_TOKEN_IS_ACCESS)
        errors += 1
    elif has_refresh and not has_device:
        print("ERROR VK_DEVICE_ID is required together with VK_REFRESH_TOKEN")
        errors += 1
    elif has_refresh:
        print("OK will refresh access_token on this host via VK ID refresh_token")
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
            client = VkClient.from_env(group_id=group_ids[0])
            for gid in group_ids:
                probe = client.with_group(gid).probe_token()
                if probe["ok"]:
                    print(
                        f"OK VK API groups.getRequests reachable group_id={gid} "
                        f"sample={probe['pending_count_sample']}"
                    )
                    continue
                code = probe.get("error_code")
                msg = probe.get("error_message")
                print(f"ERROR VK API probe failed group_id={gid}: code={code} msg={msg}")
                if code == 27:
                    print(
                        "HINT error 27: VK_ACCESS_TOKEN is a community (group) token. "
                        "groups.getRequests requires a USER token with groups scope. "
                        "See docs/how-to-get-vk-user-token.md"
                    )
                elif code == 15:
                    print(
                        "HINT error 15: token lacks groups permission or user is not group admin. "
                        "See docs/how-to-get-vk-user-token.md"
                    )
                elif code == 5:
                    print(
                        "HINT error 5 (IP): refresh access_token on THIS host with "
                        "VK_REFRESH_TOKEN + VK_DEVICE_ID (VK ID grant_type=refresh_token). "
                        "See docs/how-to-get-vk-user-token.md"
                    )
                errors += 1
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR VK client: {exc}")
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
