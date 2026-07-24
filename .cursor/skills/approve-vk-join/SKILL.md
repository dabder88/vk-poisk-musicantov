---
name: approve-vk-join
description: Approve VK join requests with safety gates.
---

# Approve VK Join Requests

## Gates

- `APPROVE_ALLOW=yes` AND `DRY_RUN=no` → live approve
- Otherwise → dry-run only

## Steps

1. `python3 scripts/approve.py --run-dir <run-dir> --run-id <run-id>`
2. Confirm `approve-results.json`
3. Ledger updated on live approve
