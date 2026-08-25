---
name: director-vk-join
description: Director skill for VK join-request automation pipeline.
---

# Director VK Join

## Input

- `AGENTS.md`
- `docs/vk-closed-group-join-requests.md`
- env: VK_GROUP_ID, VK_REFRESH_TOKEN, VK_DEVICE_ID, VK_SERVICE_TOKEN, APPROVE_ALLOW, DRY_RUN

## Steps

1. doctor.py PASS
2. start_run with unique run_id
3. Launch vk-fetch → vk-decide → vk-approve → vk-qa in order
4. fixer if open incidents

## Output contract

```text
run_id:
run_dir:
qa: PASS|FAIL
approve: dry_run|live|skipped
incident_queue: none|memory/pipeline-fix-queue.md#INC-...
```
