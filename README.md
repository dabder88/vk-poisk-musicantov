# VK Join Approver

Автоматический приём заявок в закрытую группу ВКонтакте через Cursor Cloud Agent.

## Что уже сделано

- Pipeline по шаблону `Автоматизация в Cursor (агенты).md`
- Скрипты: fetch → decide → approve → validate
- Director + subagents в `agents/` и `.cursor/agents/`
- Dry-run по умолчанию (безопасно)

## Что нужно от вас

Добавьте в **Cursor Dashboard → Cloud Agents → Secrets**:

| Secret | Что это |
|--------|---------|
| `VK_GROUP_ID` | Одна группа (без минуса). Можно не задавать, если есть `VK_GROUP_IDS` |
| `VK_GROUP_IDS` | Несколько пабликов: `111,222,333` |
| `VK_REFRESH_TOKEN` | `refresh_token` из VK ID OAuth (для Cloud Agent) |
| `VK_DEVICE_ID` | `device_id` из редиректа VK ID |
| `VK_SERVICE_TOKEN` | сервисный ключ приложения (конфиденциальное приложение) |

Опционально: `VK_CLIENT_ID` (по умолчанию `54693054`), `VK_ACCESS_TOKEN` (на облаке всё равно будет refresh).

Несколько пабликов: в `VK_GROUP_IDS` перечислите ID через запятую. Один OAuth (`VK_REFRESH_TOKEN` + `VK_DEVICE_ID`) на все группы, где вы админ.

> Не используйте ключ сообщества. Не вызывайте API облаком с access_token, полученным в браузере — будет error 5 (IP). Нужен refresh на VM.
> Инструкция: `docs/how-to-get-vk-user-token.md`

Опционально (можно позже):

| Secret | Значение | Когда |
|--------|----------|-------|
| `APPROVE_ALLOW` | `no` → `yes` | После успешного dry-run |
| `DRY_RUN` | `yes` → `no` | Вместе с `APPROVE_ALLOW=yes` для реального приёма |

## Как получить токен

Кратко: нужен **user token** с правом `groups`, обычно через приложение VK ID + запрос в поддержку VK.

Пошагово: **`docs/how-to-get-vk-user-token.md`**

## Запуск

### 1. Dry-run (первый раз)

В Cursor создайте **Automation** (или запустите Cloud Agent вручную) с промптом:

```text
Запусти VK join pipeline через Director (см. AGENTS.md).
run_id: R-manual-001
APPROVE_ALLOW=no, DRY_RUN=yes — только отчёт, без реального одобрения.
```

### 2. Реальный приём

После успешного dry-run установите Secrets:

```text
APPROVE_ALLOW=yes
DRY_RUN=no
```

Создайте Automation по расписанию (например, каждые 30 минут):

```text
Запусти VK join pipeline через Director (см. AGENTS.md).
Принять все заявки (policy approve_all).
```

## Локальная проверка

```bash
export VK_GROUP_ID=123456
export VK_REFRESH_TOKEN=your_refresh_token
export VK_DEVICE_ID=your_device_id
export VK_SERVICE_TOKEN=your_service_token
export APPROVE_ALLOW=no
export DRY_RUN=yes

python3 -m pip install -r requirements.txt
python3 scripts/doctor.py
python3 scripts/start_run.py --run-id test-001
python3 scripts/fetch_requests.py --run-dir memory/runs/test-001
python3 scripts/decide.py --run-dir memory/runs/test-001
python3 scripts/approve.py --run-dir memory/runs/test-001 --run-id test-001
python3 scripts/validate_run.py --run-dir memory/runs/test-001
```

## Если doctor падает с error 5

Access token привязан к другому IP. Положите `VK_REFRESH_TOKEN` и `VK_DEVICE_ID` в Secrets — Cloud Agent обновит токен на своей VM. См. `docs/how-to-get-vk-user-token.md`.

## Если doctor падает с error 27

Вы используете **ключ сообщества**. Замените `VK_ACCESS_TOKEN` на **user token** — см. `docs/how-to-get-vk-user-token.md`.

## Если doctor падает с error 15

У токена нет права `groups` или аккаунт не админ группы — см. `docs/how-to-get-vk-user-token.md`.

## Структура

```text
AGENTS.md              — главный контракт для Cloud Agent
scripts/               — fetch, decide, approve, doctor, validate
agents/ + .cursor/     — роли Director и subagents
shared/approve-policy.md — approve_all | manual_only
memory/approved-ledger.md — журнал одобрений
```
