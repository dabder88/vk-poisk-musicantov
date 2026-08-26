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

## INC-20260826-0552-doctor-error-5-new-vm
status: fixed
run_date: 2026-08-26
role: vk-director
run_id: none
severity: blocker
category: api

### What went wrong
- New VM, no `memory/site.env.local` at start. Dashboard secrets present: VK_GROUP_ID (3 ids), VK_REFRESH_TOKEN, VK_DEVICE_ID, VK_SERVICE_TOKEN. APPROVE_ALLOW absent (default no). DRY_RUN absent (default yes).
- One `python3 scripts/doctor.py` (no loop): VK ID refresh on this host OK (`user_id=4253689`, `scope=groups`). Hint: refresh may have rotated; copy from gitignored `memory/site.env.local` into Dashboard before the next VM (file not printed, not committed).
- Then error 5 on some groups → same-token retries → **one** extra refresh (as designed) → still error 5 on `37759698` and `37636297`. Group `12830069` OK (`sample=1`).
- Doctor FAIL errors=2. start_run / vk-fetch / vk-decide / vk-approve not started (doctor gate FAIL).
- Not `invalid_grant`. Token cache file now present (0600, gitignored).

### How the agent recovered this run
- Did not re-run doctor.
- Did not call `refresh force` again.
- Did not enable live approve.
- Secrets not logged.

### Durable fix needed before next run
- Do not loop doctor or force a third refresh on this VM (would burn Dashboard `VK_REFRESH_TOKEN`).
- After extra refresh, retry **all** groups with the new token (not only remaining IP-failed), still at most one extra refresh.
- Infra: non-sticky Cloud Agent egress IP; error 5/1130 can remain after extra refresh.
- Human: if VK rotated refresh, copy `VK_REFRESH_TOKEN` from this VM `memory/site.env.local` into Dashboard before the next Cloud Agent VM.

### Suggested files to inspect/change
- `scripts/vk_ip_refresh.py`
- `scripts/doctor.py`
- `scripts/fetch_requests.py`

### Secrets
- none recorded

### Fixer resolution
- status: fixed (code). Sticky egress remains infra; this VM still cannot PASS doctor without another force refresh.
- After one extra refresh, `run_per_group_with_one_extra_refresh` now retries **all** original `group_ids` with the new token (not only `still_ip`). Still at most one extra refresh per process.
- Cache reuse unchanged: `refresh_from_env()` without `force` uses `memory/site.env.local`; extra `force=True` only after getRequests IP retries fail.
- Tests (mock HTTP, no live OAuth): extra refresh re-probes every group; cache-hit success does not refresh; second extra refresh is a no-op.
- Fixer did **not** run `python3 scripts/doctor.py` (would extra-refresh on error 5). Did **not** call `refresh_from_env(force=True)`.
- Cache-only probe (VkClient from cache, no OAuth, no extra refresh): cache exists mode 0600; `groups.getRequests` error 5 on all 3 group ids (`ok=0/3`). Host-bound access_token no longer matches current egress IP.
- Director: **do not** re-run `doctor.py` on this VM (error 5 → another force refresh). Live approve stays off. Before next VM: copy rotated `VK_REFRESH_TOKEN` from gitignored `memory/site.env.local` into Dashboard (do not print/commit the file).

## INC-20260826-0836-director-invalid-grant
status: needs-human
run_date: 2026-08-26
role: vk-director
run_id: none
severity: blocker
category: env

### What went wrong
- New Cloud VM after previous VM asked a human to copy rotated `VK_REFRESH_TOKEN` from that VM `memory/site.env.local` into Dashboard.
- Branch with cache: `cursor/vk-join-dryrun-new-vm-39da` from `origin/cursor/vk-join-dryrun-new-vm-2af9`.
- Env (no values): `VK_GROUP_ID` present (3 ids, matches `37759698`,`12830069`,`37636297`), `VK_GROUP_IDS` absent, `VK_REFRESH_TOKEN` present, `VK_DEVICE_ID` present, `VK_SERVICE_TOKEN` present, `VK_ACCESS_TOKEN` present. `APPROVE_ALLOW` absent (doctor default no). `DRY_RUN` absent (default yes).
- No `memory/site.env.local` at start (normal for a new VM).
- One `python3 scripts/doctor.py` only: FAIL `VK ID OAuth error invalid_grant: refresh_token is missing or invalid`. No getRequests. Cache file still absent (exchange did not persist).
- start_run / vk-fetch / vk-decide / vk-approve not started (doctor gate FAIL). Not a second refresh. Not live approve.

### How the agent recovered this run
- Did not re-run doctor.
- Did not call `refresh_from_env(force=True)`.
- Did not start fetch/decide/approve.
- Secrets not logged or committed.

### Durable fix needed before next run
- **Do not fix with code.** Dashboard `VK_REFRESH_TOKEN` is dead (`invalid_grant` missing or invalid). Extra doctor/refresh will not revive it and can make things worse.
- Human: issue a new VK ID refresh (`python3 scripts/get_vk_token.py` per `docs/how-to-get-vk-user-token.md`) **or** copy a still-valid rotated refresh from `memory/site.env.local` of a VM where exchange **succeeded**, into Dashboard. Then start a **new** VM. Do not reuse this VM for doctor.
- This VM has no host cache; do not probe `VK_ACCESS_TOKEN` from Dashboard as the API source (client/IP mismatch → error 5/10).
- Fixer skill/agent currently says run `doctor.py`; for `invalid_grant` that is forbidden. Guard the fixer prompt so it marks `needs-human` and does **not** call doctor/refresh.

### Suggested files to inspect/change
- Cursor Dashboard secret `VK_REFRESH_TOKEN` (human only)
- `docs/vk-join-session-status.md`
- `.cursor/agents/vk-fixer.md`
- `.cursor/skills/fixer-vk-join/SKILL.md`
- `agents/vk-fixer.md` and `skills/fixer-vk-join/SKILL.md` if they exist as sources

### Secrets
- none recorded

### Fixer resolution
- status: needs-human. Код не чинит мёртвый Dashboard `VK_REFRESH_TOKEN` (`invalid_grant`: missing or invalid). Кэш на этой VM нет — обмен не состоялся.
- `python3 scripts/doctor.py` **не запускали**. `refresh_from_env` / `force=True` / OAuth / getRequests / approve **не вызывали**. Новый refresh/кэш не изобретали.
- Durable prompt-guard: fixer agent + skill (`.cursor/` и `agents/` / `skills/`) — при `invalid_grant` doctor и refresh запрещены, статус `needs-human`, стоп. Обычный doctor только если инцидент не про `invalid_grant`.
- Hint человеку (без секретов): выпустить новый VK ID refresh (`python3 scripts/get_vk_token.py`, `docs/how-to-get-vk-user-token.md`) **или** скопировать ещё валидный ротированный refresh из `memory/site.env.local` той VM, где обмен **удался**, в Cursor Dashboard. Затем **новая** VM. Эту VM для doctor/refresh не использовать. Не печатать и не коммитить токены. `docs/vk-join-session-status.md` обновляет Director.

## INC-20260826-1106-director-error-5-after-extra-refresh
status: needs-human
run_date: 2026-08-26
role: vk-director
run_id: none
severity: blocker
category: api

### What went wrong
- New Cloud VM d753 (Сессия 9), not 39da. Branch with cache: `cursor/vk-join-dryrun-new-vm-d753` from `origin/cursor/vk-join-dryrun-new-vm-39da`.
- Env (no values): `VK_GROUP_ID` present (3 ids, matches `37759698`,`12830069`,`37636297`), `VK_GROUP_IDS` absent, `VK_REFRESH_TOKEN` present, `VK_DEVICE_ID` present, `VK_SERVICE_TOKEN` present, `VK_ACCESS_TOKEN` present. `APPROVE_ALLOW` absent (default no). `DRY_RUN` absent (default yes).
- No `memory/site.env.local` at start (normal for a new VM). Snapshot install doctor on `main` earlier failed at CSV parse (`int()`); that build did not complete OAuth.
- One `python3 scripts/doctor.py` only on this VM: VK ID refresh OK (`user_id=4253689`, `scope=groups`). Cache file created (0600, gitignored). Then getRequests error 5 → same-token retries → **one** extra refresh (as designed, retry **all** groups) → still error 5 on `37759698` and `12830069`. Group `37636297` OK (`sample=1`). Doctor FAIL errors=2.
- start_run / vk-fetch / vk-decide / vk-approve not started (doctor gate FAIL). Not a second doctor. Not live approve. Not `invalid_grant`.
- Same infra class as INC-0552: Cloud Agent egress IP is not sticky. Extra-refresh-all code already landed; this is not a missing retry-all bug.

### How the agent recovered this run
- Did not re-run doctor.
- Did not call `refresh force` again.
- Did not start fetch/decide/approve.
- Secrets not logged or committed.

### Durable fix needed before next run
- **Do not** re-run `doctor.py` or `refresh force` on this VM (would burn rotated refresh).
- Do **not** invent a new cache/refresh path. INC-0552 already retries all groups after one extra refresh.
- Infra: non-sticky Cloud Agent egress; error 5 can remain after extra refresh. Dry-run must run on the person's PC (one IP, disk cache). Do not spawn another Cloud VM «на всякий случай».
- `.cursor/environment.json` `install` still runs `python3 scripts/doctor.py || true` on snapshot builds (can exchange/burn refresh before the agent starts). Remove doctor from install; doctor is a Director gate, not image setup.
- Human: copy rotated `VK_REFRESH_TOKEN` from this VM `memory/site.env.local` into Dashboard **only if** another cloud run is actually needed. Preferred next step: one `python3 scripts/doctor.py` on the PC (branch with cache), then pipeline there. Do not print or commit the cache file.

### Suggested files to inspect/change
- `.cursor/environment.json`
- `.cursor/agents/vk-fixer.md`
- `.cursor/skills/fixer-vk-join/SKILL.md`
- `skills/fixer-vk-join/SKILL.md`
- `docs/vk-join-session-status.md` (Director updates at end)

### Secrets
- none recorded

### Fixer resolution
- status: needs-human. Код не чинит sticky egress IP Cloud Agent. Error 5 после одного extra refresh (retry-all уже в коде, INC-0552) — infra, не `fixed`.
- `.cursor/environment.json` `install`: убран `python3 scripts/doctor.py || true`. Остался только `pip install -r requirements.txt`. Doctor — gate Director, не snapshot install (install doctor сжигал refresh до старта агента).
- Durable prompt-guard: fixer agent + skill (`.cursor/` и `agents/` / `skills/`) — hard-stop не только на `invalid_grant`, но и на **error 5 после одного extra refresh**: doctor/refresh запрещены, статус `needs-human` (infra / dry-run на ПК), стоп. `vk_oauth` / `vk_client` / кэш не переписывали.
- `python3 scripts/doctor.py` **не запускали**. `refresh_from_env` / `force=True` / OAuth / getRequests / approve **не вызывали**. Новый refresh/кэш не изобретали. Live не включали. INC-0836 не трогали (`needs-human`).
- Hint человеку (без секретов): dry-run на ПК (один IP, disk cache). Скопировать ротированный `VK_REFRESH_TOKEN` из gitignored `memory/site.env.local` этой VM в Dashboard **только если** снова понадобится облако. Файл не печатать и не коммитить. Не поднимать ещё одну Cloud VM «на всякий случай». `docs/vk-join-session-status.md` обновляет Director.
