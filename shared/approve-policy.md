mode: approve_all

# Политика автоприёма заявок

## Режимы

| mode | Поведение |
|------|-----------|
| `approve_all` | Одобрять все заявки из `groups.getRequests` |
| `manual_only` | Не одобрять автоматически (только fetch + отчёт) |

## Текущий режим

`approve_all` — принимать всех подавших заявку.

## Будущие расширения

- whitelist по `user_id`
- фильтр по полям профиля (`fields` в `groups.getRequests`)
- AI-модерация через subagent `vk-decide`
