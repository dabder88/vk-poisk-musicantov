---
name: fetch-vk-join
description: Fetch VK group join requests.
---

# Fetch VK Join Requests

## Steps

1. Verify run dir exists
2. `python3 scripts/fetch_requests.py --run-dir <run-dir>`
3. Confirm `requests.json` created

## Output

`requests.json` with `groups[]` (`group_id`, `user_ids`) and total `count`.
