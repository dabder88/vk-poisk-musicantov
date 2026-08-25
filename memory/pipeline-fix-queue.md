# Pipeline fix queue

Incidents are appended below by agents when blockers occur.

## INC-20260825-1255-director-refresh-token-is-access
status: needs-human
run_date: 2026-08-25
role: vk-director
run_id: R20260825-1255
severity: blocker
category: env

### What went wrong
- `python3 scripts/doctor.py` FAIL: VK ID `invalid_grant` (refresh_token missing or invalid).
- `VK_REFRESH_TOKEN` present (len=261) but prefix `vk2.a.` — это access_token, не refresh_token (ожидается `vk2.r.`).
- `VK_ACCESS_TOKEN` тоже `vk2.a.`; `groups.getRequests` без refresh → error 5 (token bound to another IP / 1130).
- Env present: `VK_GROUP_ID` (3 ids), `VK_REFRESH_TOKEN`, `VK_DEVICE_ID`, `VK_SERVICE_TOKEN`. `VK_CLIENT_ID` unset (default 54693054). `VK_GROUP_IDS` unset.
- Fetch/decide/approve не запускались: doctor gate FAIL. Dry-run flags: `APPROVE_ALLOW=no`, `DRY_RUN=yes`.

### How the agent recovered this run
- Не recovered: без валидного refresh_token на этой VM API недоступен.
- Варианты OAuth (без scope / без service_token / расширенный scope) — тот же `invalid_grant`.

### Durable fix needed before next run
- Человек: в Cursor Secrets положить **refresh_token** из ответа VK ID (`vk2.r.…`), не access_token. Получение: `python3 scripts/get_vk_token.py start` → `finish --redirect-url ...`. После refresh обновить секрет, если VK ротирует refresh.
- Код: `doctor.py` должен FAIL с HINT, если `VK_REFRESH_TOKEN` имеет prefix access_token (`vk2.a.`).

### Suggested files to inspect/change
- `scripts/doctor.py`
- `docs/how-to-get-vk-user-token.md`
- Cursor Dashboard secrets: `VK_REFRESH_TOKEN`

### Secrets
- none recorded

### Fixer resolution
- durable code: **fixed** — `scripts/doctor.py` FAIL + HINT if `VK_REFRESH_TOKEN` starts with `vk2.a.`; HTTP/refresh не вызывается. Документация и `tests/test_doctor.py` обновлены.
- секрет Dashboard: **needs-human** — `VK_REFRESH_TOKEN` всё ещё access_token (`vk2.a.`). Заменить на refresh_token VK ID (`vk2.r.…`) из `python3 scripts/get_vk_token.py start` затем `finish --redirect-url ...`. Не класть `vk2.a.` в refresh.
- doctor после патча: FAIL, errors=1, новый HINT (ожидаемо, пока секрет неверный). Live-approve не выполнялся.
