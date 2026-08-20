# VK Join Approver — Cloud Instructions

Язык работы: русский.

## Назначение

Автоматически принимать заявки на вступление в **закрытую** группу ВКонтакте по расписанию (Cursor Automation).

## Главное правило

Полный pipeline нельзя выполнять одним агентом. Cloud Agent работает как **Director** и запускает роли:

```text
doctor + start_run
  → vk-fetch
  → vk-decide
  → vk-approve
  → vk-qa
  → vk-fixer (если есть open incidents)
```

## Что считать ошибкой

- Parent сам делает работу роли вместо subagent.
- Следующий этап стартует без PASS gate предыдущего.
- `approve` при `APPROVE_ALLOW=no` или `DRY_RUN=yes` — только dry-run, не live.
- Secrets попали в handoff/commit/log.

## Canonical paths

| Artifact | Path |
|----------|------|
| Research | `docs/vk-closed-group-join-requests.md` |
| Policy | `shared/approve-policy.md` |
| Agents source | `agents/` |
| Cloud agents | `.cursor/agents/` |
| Skills source | `skills/` |
| Cloud skills | `.cursor/skills/` |
| Shared contracts | `shared/` |
| Scripts/gates | `scripts/` |
| Runtime memory | `memory/` |
| Incident queue | `memory/pipeline-fix-queue.md` |
| Approved ledger | `memory/approved-ledger.md` |

## Preflight

```bash
python3 scripts/doctor.py
python3 scripts/start_run.py --run-id <id>
python3 scripts/fetch_requests.py --run-dir memory/runs/<id>
python3 scripts/decide.py --run-dir memory/runs/<id>
python3 scripts/approve.py --run-dir memory/runs/<id> --run-id <id>
python3 scripts/validate_run.py --run-dir memory/runs/<id> -o memory/runs/<id>/qa.json
```

## Secrets (только Cursor Dashboard)

Required:

- `VK_GROUP_ID` — числовой ID группы (без минуса)
- `VK_ACCESS_TOKEN` — **user access token** с правом `groups` (VK ID OAuth 2.1 + PKCE; не ключ сообщества). Инструкция: `docs/how-to-get-vk-user-token.md`

Optional:

- `VK_API_VERSION` — по умолчанию `5.199`
- `APPROVE_ALLOW` — `no` (по умолчанию) или `yes` для реального одобрения
- `DRY_RUN` — `yes` (по умолчанию) или `no` вместе с `APPROVE_ALLOW=yes`

## Incident memory

Если агент встретил blocker/retry/tool error/workaround, он пишет incident в:

`memory/pipeline-fix-queue.md`

Формат: `shared/pipeline-incident-fix-contract.md`
