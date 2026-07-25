# VK Join Approver

Автоматический приём заявок в закрытую группу ВКонтакте через Cursor Cloud Agent.

## Что уже сделано

- Pipeline по шаблону `Автоматизация в Cursor (агенты).md`
- Скрипты: fetch → decide → approve → validate
- Director + subagents в `agents/` и `.cursor/agents/`
- Dry-run по умолчанию (безопасно)

## Что нужно от вас (2 значения)

Добавьте в **Cursor Dashboard → Cloud Agents → Secrets**:

| Secret | Что это |
|--------|---------|
| `VK_GROUP_ID` | Числовой ID группы (без минуса). Например, для `vk.com/club123456` → `123456` |
| `VK_ACCESS_TOKEN` | **User token** администратора группы с правом `groups` (НЕ ключ сообщества из «Ключи доступа») |

> Ключ из **Работа с API → Ключи доступа** не подходит — VK вернёт error 27.
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
export VK_ACCESS_TOKEN=your_token
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
