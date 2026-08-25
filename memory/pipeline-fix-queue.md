# Pipeline fix queue

Incidents are appended below by agents when blockers occur.

## INC-20260825-1526-director-refresh-not-cached
status: fixed
run_date: 2026-08-25
role: vk-director
run_id: none
severity: blocker
category: api

### What went wrong
- Env OK: VK_GROUP_ID (3 ids), VK_REFRESH_TOKEN, VK_DEVICE_ID, VK_SERVICE_TOKEN present. VK_CLIENT_ID missing in Dashboard (session default 54693054). APPROVE_ALLOW=no DRY_RUN=yes.
- First `python3 scripts/doctor.py`: VK ID refresh on this host OK (`user_id=4253689`, `scope=groups`). Then `groups.getRequests` for 2 of 3 groups returned error 5 (token given to another IP); 1 group reachable (sample=1). Doctor FAIL (errors=2).
- Second doctor immediately: `invalid_grant: session is compromised because refresh token has already been applied`.
- Later refresh: `invalid_grant: refresh_token is missing or invalid`.
- Probe with env `VK_ACCESS_TOKEN` and `refresh=False`: error 10 on all 3 groups (could not check access_token).
- Root durable bug: `VkClient.from_env(refresh=True)` exchanges refresh on every process (doctor, fetch, approve). Rotated `refresh_token`/`access_token` are discarded. Cloud Agent cannot write Cursor Dashboard secrets. Next stage or retry burns/invalidates the Dashboard `VK_REFRESH_TOKEN`.
- Possible extra issue: non-sticky egress IP so some API calls after a successful refresh still see error 5; probes should retry with the same in-memory token, not a second refresh.

### How the agent recovered this run
- Did not start_run / vk-fetch / vk-decide / vk-approve (doctor gate FAIL).
- Did not enable live approve.
- Secrets not logged.

### Durable fix needed before next run
- After a successful refresh, persist tokens to gitignored `memory/site.env.local` (mode 0600). Never commit tokens. Never print them.
- `from_env` must refresh **at most once**, then reuse cached `access_token` for fetch/approve/doctor retries in the same VM.
- If VK returns a new `refresh_token`, write it only to `memory/site.env.local`. Print a no-secret hint that Dashboard `VK_REFRESH_TOKEN` must be updated from that local file by a human before the next Cloud Agent VM.
- On API error 5/1130: retry getRequests with the cached host-bound token (2–3 times). Do **not** call refresh again unless cache is empty or probe still fails after retries.
- doctor must PASS getRequests on **each** of the 3 groups after one refresh.
- Human: Dashboard `VK_REFRESH_TOKEN` is now invalid; re-run `python3 scripts/get_vk_token.py` on a PC and update secrets. This run cannot complete without a new refresh_token.

### Suggested files to inspect/change
- `scripts/vk_client.py`
- `scripts/vk_oauth.py`
- `scripts/doctor.py`
- `scripts/fetch_requests.py`
- `scripts/approve.py`
- `tests/test_vk_oauth.py`
- `docs/how-to-get-vk-user-token.md`
- `.gitignore` (`memory/site.env.local` already ignored)

### Secrets
- none recorded

### Fixer resolution
- Cache/reuse/retry **code fix is in working tree** (`status: fixed` for this durable bug).
- `refresh_from_env`: HTTP exchange at most once unless `force=True`; persist to `memory/site.env.local` (0600); later `from_env` reuses cached `access_token`.
- Rotated `refresh_token` written only to that gitignored file; stdout hint has no secrets.
- `groups.getRequests` retries 3 times on error 5/1130 with the same token; doctor may force one extra refresh after retries, not a loop.
- Tests (mock HTTP): cache reuse, no second refresh, meta/hint files without secrets.
- This VM doctor after the fix: **FAIL** `invalid_grant` (`refresh_token is missing or invalid`), one attempt, no refresh loop. Dashboard token remains burned — see INC-20260825-1545-dashboard-refresh-invalid.

## INC-20260825-1545-dashboard-refresh-invalid
status: needs-human
run_date: 2026-08-25
role: vk-fixer
run_id: none
severity: blocker
category: env

### What went wrong
- Cursor Secret `VK_REFRESH_TOKEN` was already consumed/invalidated on this VM before the cache fix (`invalid_grant`: already applied, then missing or invalid).
- Code cache cannot recover: there is no valid host-bound token in `memory/site.env.local` from a successful refresh on this run.

### How the agent recovered this run
- Durable cache/retry patch landed; did not loop refresh; did not start fetch/decide/approve; `APPROVE_ALLOW` left at `no`.

### Durable fix needed before next run
- Human: on a PC run `python3 scripts/get_vk_token.py start` / `finish`, put new `VK_REFRESH_TOKEN` + `VK_DEVICE_ID` (+ `VK_SERVICE_TOKEN`) into Cursor Dashboard secrets.
- Next Cloud Agent: first doctor refresh once, write `memory/site.env.local`, copy rotated refresh from that file into Dashboard **before the next VM** if VK rotated it.

### Suggested files to inspect/change
- Cursor Dashboard secrets (not in git)
- `docs/how-to-get-vk-user-token.md`

### Secrets
- none recorded

### Fixer resolution
- needs-human: new `VK_REFRESH_TOKEN` in Dashboard. Code-side cache is `fixed` in INC-20260825-1526.

## INC-20260825-1552-fetch-error-5-ip
status: open
run_date: 2026-08-25
role: vk-fetch
run_id: R20260825-1552
severity: blocker
category: api

### What went wrong
- Doctor was already PASS. vk-fetch reused gitignored `memory/site.env.local` (`from_cache`, no `refresh force`, doctor not run).
- `python3 scripts/fetch_requests.py --run-dir memory/runs/R20260825-1552` with `APPROVE_ALLOW=no` `DRY_RUN=yes`.
- First attempt: group `37759698` getRequests OK (`pending=70`); group `12830069` then VK error 5 (`access_token was given to another ip address`). Script aborted; `requests.json` not written.
- Immediate retry (same cache, no force): error 5 on the first group. Client already retries getRequests 3 times on 5/1130 with the same token.
- Groups `37636297` not reached. No force refresh per fetch instructions.

### How the agent recovered this run
- Did not call `refresh_from_env(force=True)`, doctor, `run_pipeline.sh`, decide, or approve.
- Did not print or commit token cache contents.
- Handoff marked FAIL; incident recorded.

### Durable fix needed before next run
- Sticky egress IP for the VM so a host-cached access_token stays valid for all 3 `groups.getRequests` calls.
- Optional: write partial `requests.json` / continue other groups after error 5 instead of aborting the whole fetch.
- Do not force-refresh on error 5 if cache exists (burns `VK_REFRESH_TOKEN`).

### Suggested files to inspect/change
- `scripts/fetch_requests.py`
- `scripts/vk_client.py`
- Cloud Agent egress / environment network

### Secrets
- none recorded

### Fixer resolution
- pending
