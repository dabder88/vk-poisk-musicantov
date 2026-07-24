# VK Join Approver

Автоматический приём заявок в закрытую группу ВКонтакте через Cursor Cloud Agent.

## Что уже сделано

- Pipeline по шаблону `Автоматизация в Cursor (агенты).md`
- Скрипты: fetch → decide → approve → validate
- Director + subagents в `agents/` и `.cursor/agents/`
- Dry-run по умолчанию (безопасно)

## Что нужно от вас (2 значения)

Добавьте в **Cursor Dashboard → Cloud Agents → Secrets** для этого репозитория:

| Secret | Что это |
|--------|---------|
| `VK_GROUP_ID` | Числовой ID группы (без минуса). Например, для `vk.com/club123456` → `123456` |
| `VK_ACCESS_TOKEN` | Ключ из группы: **Управление → Дополнительно → Работа с API → Ключи доступа → Создать ключ** с правом **«Управление сообществом»** |

Опционально (можно позже):

| Secret | Значение | Когда |
|--------|----------|-------|
| `APPROVE_ALLOW` | `no` → `yes` | После успешного dry-run |
| `DRY_RUN` | `yes` → `no` | Вместе с `APPROVE_ALLOW=yes` для реального приёма |

## Как получить токен (30 секунд)

1. Откройте вашу группу ВК (вы — администратор)
2. **Управление → Дополнительно → Работа с API**
3. Вкладка **Ключи доступа → Создать ключ**
4. Отметьте **Управление сообществом** (manage)
5. Подтвердите в приложении ВК
6. Скопируйте ключ → вставьте в `VK_ACCESS_TOKEN` в Cursor Secrets

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

## Если doctor падает с error 15 или 27

Токен не подходит для `groups.getRequests`. Напишите в issue — понадобится user token со scope `groups` (через поддержку VK). Подробности: `docs/vk-closed-group-join-requests.md`.

## Структура

```text
AGENTS.md              — главный контракт для Cloud Agent
scripts/               — fetch, decide, approve, doctor, validate
agents/ + .cursor/     — роли Director и subagents
shared/approve-policy.md — approve_all | manual_only
memory/approved-ledger.md — журнал одобрений
```
