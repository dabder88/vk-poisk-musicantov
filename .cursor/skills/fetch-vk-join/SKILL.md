---
name: fetch-vk-join
description: Fetch VK group join requests.
---

# Fetch VK Join Requests

## Steps

1. Verify run dir exists
2. `python3 scripts/fetch_requests.py --run-dir <run-dir>`
3. Confirm `requests.json` created (even if some groups failed)

## Output

`requests.json` with `groups[]` (`group_id`, `user_ids`) and total `count`.
Failed groups keep `error_code` and empty `user_ids`; `partial=true` if any error.
On error 5/1130: client retries the same token, then at most one extra refresh (`force=True`) and remaining groups. Do not loop refresh. Do not run doctor.
