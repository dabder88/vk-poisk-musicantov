---
name: decide-vk-join
description: Decide which requests to approve per policy.
---

# Decide VK Join Requests

## Steps

1. Read `shared/approve-policy.md` mode
2. `python3 scripts/decide.py --run-dir <run-dir>`
3. Confirm `decision.json` with `to_approve` and `skipped`
