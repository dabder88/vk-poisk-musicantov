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
status: fixed
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
- Later this VM: doctor PASS (refresh OK, `user_id=4253689`, `scope=groups`). Secret was rotated/updated; host cache reused by fetch.

### Durable fix needed before next run
- Human: copy rotated `VK_REFRESH_TOKEN` from gitignored `memory/site.env.local` into Cursor Dashboard **before the next Cloud Agent VM**. Do not print or commit the file.
- Do not re-run `doctor.py` / `refresh force` on this VM just to “refresh secrets”; extra exchange can `invalid_grant`.

### Suggested files to inspect/change
- Cursor Dashboard secrets (not in git)
- `docs/how-to-get-vk-user-token.md`

### Secrets
- none recorded

### Fixer resolution
- status: fixed (secret updated on this run; doctor PASS).
- Before next VM: copy rotated refresh from `memory/site.env.local` into Dashboard (no file dump).

## INC-20260825-1552-fetch-error-5-ip
status: fixed
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
- Sticky egress IP for the VM so a host-cached access_token stays valid for all 3 `groups.getRequests` calls (infra; cannot be fully fixed in code).
- Write partial `requests.json` / continue other groups after error 5 instead of aborting the whole fetch.
- One extra `refresh force=True` only after IP retries are exhausted, once per process — not a loop, not a second refresh on first error 5.

### Suggested files to inspect/change
- `scripts/fetch_requests.py`
- `scripts/vk_ip_refresh.py`
- `scripts/vk_client.py`
- Cloud Agent egress / environment network

### Secrets
- none recorded

### Fixer resolution
- status: fixed (code). Sticky egress remains an infra note.
- Shared helper `scripts/vk_ip_refresh.py`: same-token getRequests retries, then **one** extra refresh, then remaining groups (used by fetch + doctor; live approve recovers one IP error the same way).
- `fetch_requests.py` always writes `requests.json`; failed groups get `error_code` + empty `user_ids`; `partial=true` if any error. Does not abort before write.
- Extra refresh is not called on cache-hit success. Not a second refresh on the first error 5.
- Infra: non-sticky egress can still yield error 5 after cache reuse; next vk-fetch may use one extra refresh without re-running doctor.

## INC-20260826-0625-live-refresh-already-applied
status: needs-human
run_date: 2026-08-26
role: vk-director
run_id: none
severity: blocker
category: env

### What went wrong
- User asked for live approve (`APPROVE_ALLOW=yes` `DRY_RUN=no` in this process; Dashboard at VM boot was still no/yes).
- Cache `memory/site.env.local` still present from 2026-08-25. Doctor reused cached access_token (no refresh), then getRequests needed extra refresh (error 5/1130).
- Extra refresh: `invalid_grant: session is compromised because refresh token has already been applied`. That refresh was already exchanged on this VM yesterday. Second doctor was not run.
- Dashboard `VK_REFRESH_TOKEN` update does not reload into an already running Cloud Agent. Live fetch/approve not started.

### How the agent recovered this run
- Stopped at doctor FAIL. No start_run, no fetch/decide/approve, no doctor loop, no live API approve.
- Secrets not logged.

### Durable fix needed before next run
- Start a **new** Cloud Agent after Dashboard secrets are saved (this VM cannot refresh again).
- Dashboard: `APPROVE_ALLOW=yes` and `DRY_RUN=no` before that new agent starts, plus current `VK_REFRESH_TOKEN` / `VK_DEVICE_ID`.
- Do not re-run doctor on this VM.

### Suggested files to inspect/change
- Cursor Dashboard secrets (not in git)
- new Cloud Agent session (not this VM)

### Secrets
- none recorded

### Fixer resolution
- needs-human: new Cloud Agent with updated secrets. Code cache is fine; this VM's refresh is spent.
