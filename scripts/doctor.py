#!/usr/bin/env python3
"""Preflight checks for VK join-request pipeline."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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

REQUIRED_ENV = [
    "VK_GROUP_ID",
    "VK_ACCESS_TOKEN",
]

OPTIONAL_ENV = [
    "VK_API_VERSION",
    "APPROVE_ALLOW",
    "DRY_RUN",
]


def check_env(name: str) -> tuple[bool, str]:
    value = os.environ.get(name, "").strip()
    if not value:
        return False, f"MISSING env {name}"
    return True, f"OK env {name} configured"


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

    for name in REQUIRED_ENV:
        ok, msg = check_env(name)
        print(msg)
        if not ok:
            errors += 1

    for name in OPTIONAL_ENV:
        value = os.environ.get(name, "").strip()
        if value:
            print(f"OK env {name} configured")
        else:
            print(f"WARN env {name} not set (using default)")
            warnings += 1

    approve_allow = os.environ.get("APPROVE_ALLOW", "no").strip().lower()
    if approve_allow not in ("yes", "no"):
        print("ERROR APPROVE_ALLOW must be yes or no")
        errors += 1
    else:
        print(f"OK APPROVE_ALLOW={approve_allow}")

    if errors == 0:
        try:
            client = VkClient.from_env()
            probe = client.probe_token()
            if probe["ok"]:
                print("OK VK API groups.getRequests reachable")
                print(f"OK sample pending requests: {probe['pending_count_sample']}")
            else:
                print(
                    f"ERROR VK API probe failed: "
                    f"code={probe.get('error_code')} msg={probe.get('error_message')}"
                )
                errors += 1
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR VK client: {exc}")
            errors += 1

    print(f"SUMMARY errors={errors} warnings={warnings}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
