---
name: director-vk-join
description: Director skill for VK join-request automation pipeline.
---

# Director VK Join

## Input

- `AGENTS.md`
- `docs/vk-closed-group-join-requests.md`
- env: VK_GROUP_ID, VK_GROUP_IDS, VK_REFRESH_TOKEN, VK_DEVICE_ID, VK_SERVICE_TOKEN, APPROVE_ALLOW, DRY_RUN

## Steps

1. doctor.py PASS (one refresh per VM; tokens in gitignored `memory/site.env.local`)
2. start_run with unique run_id
3. Launch vk-fetch → vk-decide → vk-approve → vk-qa in order (reuse cache, no second refresh)
4. fixer if open incidents
5. Do not loop doctor on `invalid_grant`; Dashboard `VK_REFRESH_TOKEN` needs a human update

## Output contract

```text
run_id:
run_dir:
qa: PASS|FAIL
approve: dry_run|live|skipped
incident_queue: none|memory/pipeline-fix-queue.md#INC-...
```
