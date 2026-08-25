# Исследование: автоприём заявок в закрытую группу ВК через Cursor Cloud Agent

Дата: 2026-07-24  
Источники: [dev.vk.com](https://dev.vk.com) (июль 2026), внутренний шаблон `Автоматизация в Cursor (агенты).md`

---

## 1. Вердикт

**Задача реализуема через VK API.** Есть методы для списка заявок и их одобрения, а также событие `group_join` с `join_type=request` в Callback / Bots Long Poll.

**Главный риск — авторизация.** По актуальной документации `groups.getRequests`, `groups.approveRequest` и `groups.removeUser` принимают **только пользовательский** access token с правом `groups` (расширенное право, выдаётся через поддержку / согласование). Ключ сообщества из «Работа с API → Ключи доступа» для этих методов **официально не указан**. Перед разработкой обязателен smoke-тест токена.

**Лучший fit для Cursor Cloud Automations** (периодический запуск): **polling по расписанию** через `groups.getRequests` + `groups.approveRequest`. Callback и Long Poll требуют постоянно доступный endpoint/процесс — Cloud Agent для этого не подходит как runtime.

---

## 2. Что есть в настройках группы ВК

Путь: **Управление → Дополнительно → Работа с API**

| Вкладка | Назначение для задачи |
|---------|------------------------|
| **Ключи доступа** | Community token (бессрочный). Права: `messages`, `manage`, `photos`, `docs`, `stories`… Нужен для Long Poll / Callback-настроек. Для approve/getRequests — **проверить эмпирически**; по docs методов — не заявлен. |
| **Callback API** | VK шлёт HTTP POST на ваш сервер при событиях. Нужен публичный HTTPS endpoint. До 10 серверов. |
| **Long Poll API** | Очередь событий на стороне VK; клиент держит long-poll (`wait≤90`, обычно 25). Нужен постоянно живой процесс. |

---

## 3. API: заявки на вступление

### 3.1. Получить заявки — `groups.getRequests`

- Документация: https://dev.vk.com/ru/method/groups.getRequests  
- Параметры: `group_id` (без минуса), `offset`, `count`, `fields`  
- Результат: список `user_id` (или объекты пользователей при `fields`)  
- Токен по docs: **user token + scope `groups`** (исключительная выдача через `devsupport@corp.vk.com`)

### 3.2. Одобрить — `groups.approveRequest`

- Документация: https://dev.vk.com/ru/method/groups.approveRequest  
- Параметры: `group_id`, `user_id`  
- Результат: `1`  
- Токен по docs: **user token + scope `groups`**  
- Ошибка `103 Out of limits` — лимиты VK

### 3.3. Отклонить заявку — `groups.removeUser`

- Документация: https://dev.vk.com/ru/method/groups.removeUser  
- Исключает участника **или отклоняет заявку**  
- Токен по docs: **user token + scope `groups`**

### 3.4. Событие заявки — `group_join`

В Callback / Bots Long Poll:

```json
{
  "type": "group_join",
  "object": {
    "user_id": 1,
    "join_type": "request"
  },
  "group_id": 1
}
```

Значения `join_type` (актуальная схема событий сообщества):

| Значение | Смысл |
|----------|--------|
| `join` | Вступил / подписался |
| `request` | **Подал заявку** (закрытая группа) |
| `approved` | Заявка уже одобрена админом |
| `accepted` | Принял приглашение |
| `unsure` | Мероприятие: «Возможно, пойду» |

Важно: при `join_type=request` пользователь **ещё не участник**. Чтобы принять — вызвать `groups.approveRequest`. Событие `approved` — уже после принятия.

---

## 4. Токены: актуальные ограничения (2024–2026)

| Тип ключа | Срок | Где взять | Для approve/getRequests |
|-----------|------|-----------|-------------------------|
| **Ключ сообщества** | Бессрочный | Работа с API → Создать ключ | По docs методов — **не указан**. Smoke-тест обязателен. `manage` нужен для Long Poll server. |
| **Ключ пользователя** | Обычно ~1 час (VK ID); `offline` — legacy/исключения | VK ID / Standalone | **Официально требуется** + scope `groups` |
| **Сервисный ключ приложения** | Бессрочный | Настройки приложения | Не подходит для админ-действий от имени админа группы |

Дополнительно:

- Implicit Flow для **user** token отключён с **25.06.2024**. Новые user-токены — через **VK ID**.
- Scope `groups` относится к расширенным; часть прав согласуется индивидуально (`devsupport@corp.vk.com` / бизнес-профиль VK ID).
- Есть публичные кейсы 2025–2026, где расширенные доступы **перестали выдавать**. Это блокер №1 для production — проверить до проектирования pipeline.

### Smoke-тест (сделать до кода агента)

```bash
# 1) Список заявок
curl -s "https://api.vk.com/method/groups.getRequests" \
  -d "group_id=$VK_GROUP_ID" \
  -d "count=10" \
  -d "access_token=$VK_ACCESS_TOKEN" \
  -d "v=5.199"

# 2) Одобрение (dry-run: только если есть тестовая заявка)
curl -s "https://api.vk.com/method/groups.approveRequest" \
  -d "group_id=$VK_GROUP_ID" \
  -d "user_id=$TEST_USER_ID" \
  -d "access_token=$VK_ACCESS_TOKEN" \
  -d "v=5.199"
```

Интерпретация:

- `response: [...]` / `1` → токен пригоден  
- `error_code: 15` → нет scope / не тот тип токена  
- `error_code: 27` → метод недоступен с group auth  
- `error_code: 5` → токен невалиден / истёк / **другой IP** (нужен refresh_token на том хосте, где вызывается API)  

---

## 5. Варианты реализации

### Вариант A — Periodic polling + Cursor Automation (рекомендуемый)

**Идея:** по cron Cloud Agent поднимается, читает заявки, (опционально) фильтрует ИИ-логикой, одобряет, пишет ledger, коммитит отчёт.

```text
Cursor Automation (schedule)
  → Cloud VM clones repo
  → doctor.py (env + VK API ping)
  → Director
       → fetch-requests   (groups.getRequests)
       → decide           (правила / AI moderation)
       → approve          (groups.approveRequest)
       → qa / ledger
       → fixer при incidents
```

**Плюсы**

- Совпадает с формулировкой «с определенной периодичностью»
- Не нужен публичный webhook и всегда-on процесс
- Полностью ложится на шаблон из `Автоматизация в Cursor (агенты).md`
- Легко dry-run (`APPROVE_ALLOW=no`)

**Минусы**

- Задержка = период cron (5–60 мин обычно достаточно)
- Нужен рабочий user token (или подтверждённый community token)
- User token может истекать → нужен refresh / мониторинг

**Когда выбирать:** почти всегда для Cursor Cloud.

---

### Вариант B — Callback API (событийный)

**Идея:** VK POST’ит `group_join`/`request` на ваш HTTPS → handler сразу (или ставит в очередь) вызывает `approveRequest`.

**Плюсы:** почти real-time; меньше лишних API-вызовов.

**Минусы для Cloud Agent:**

- Cloud Agent — **не** всегда-on HTTP server
- Нужен отдельный runtime: VPS, Cloud Functions, Cloudflare Worker, и т.п.
- Подтверждение сервера (`confirmation`), secret, ответ `ok` за короткое время

**Гибрид:** Callback только кладёт `user_id` в очередь/файл/issue; Cursor Automation по расписанию обрабатывает очередь с AI-решением.

---

### Вариант C — Bots Long Poll (постоянный worker)

**Идея:** процесс в цикле: `groups.getLongPollServer` → `a_check&wait=25` → на `join_type=request` approve.

**Плюсы:** real-time без публичного URL; очередь на стороне VK.

**Минусы:** нужен 24/7 процесс; Cloud Agent ephemeral VM не подходит как host. Community token с `manage` подходит для `getLongPollServer`, но approve всё равно упирается в auth-ограничение п.4.

---

### Вариант D — Внешний сервис + Cloud Agent как «мозг»

```text
Always-on VK adapter (Callback или Long Poll)
  → очередь заявок (JSON / DB / Git issue)
Cursor Automation
  → читает очередь
  → AI-фильтр (спам, анкета, ответы на вопросы)
  → approve / reject через API
  → ledger + PR/commit отчёта
```

**Когда:** нужна сложная модерация + низкая задержка детекта, а Cloud — только для решений.

---

## 6. Рекомендуемая архитектура под Cursor (по шаблону репо)

Следовать `Автоматизация в Cursor (агенты).md`:

```text
vk-join-approver/
  AGENTS.md
  .cursor/environment.json
  .cursor/agents/   + agents/
  .cursor/skills/   + skills/
  shared/
    pipeline-handoff.template.md
    pipeline-incident-fix-contract.md
    approve-policy.md          # правила автоприёма
  scripts/
    doctor.py                  # env + api.vk.com ping + token probe
    start_run.py
    fetch_requests.py          # groups.getRequests
    decide.py                  # policy / optional AI
    approve.py                 # groups.approveRequest (gate: APPROVE_ALLOW)
    validate_run.py
  memory/
    pipeline-fix-queue.md
    runs/
    approved-ledger.md         # без PII сверх необходимого
```

### Roles

| Role | Задача |
|------|--------|
| `vk-director` | Оркестрация, gates, fixer |
| `vk-fetch` | Собрать заявки + профили |
| `vk-decide` | Применить policy (whitelist, антиспам, ответы) |
| `vk-approve` | Вызвать API только при PASS и `APPROVE_ALLOW=yes` |
| `vk-qa` | Сверить ledger, лимиты, ошибки API |
| `vk-fixer` | Durable-фиксы по incidents |

### Secrets (только Cursor Dashboard)

```text
VK_GROUP_ID=
VK_ACCESS_TOKEN=          # user token с groups ИЛИ community после smoke-теста
VK_API_VERSION=5.199
APPROVE_ALLOW=no|yes
DRY_RUN=yes|no
```

Не коммитить токены. В артефактах — `[REDACTED]`.

### Automation prompt (эскиз)

```text
Запусти pipeline автоприёма заявок ВК через Director.
1. Прочитай AGENTS.md и docs/vk-closed-group-join-requests.md
2. python3 scripts/doctor.py
3. start_run → fetch → decide → (approve только если APPROVE_ALLOW=yes) → qa
4. При open incidents → fixer
Запрещено: single-agent full pipeline; approve без gate; секреты в commit/log.
```

### Расписание

Стартовать с **1 раз / 15–60 мин**. Учитывать rate limits VK и ошибку `103`.

---

## 7. Сравнение вариантов (кратко)

| Критерий | A Polling+Automation | B Callback | C Long Poll | D Hybrid |
|----------|----------------------|------------|-------------|----------|
| Fit Cursor Cloud | ★★★★★ | ★★ | ★ | ★★★★ |
| Задержка | минуты | секунды | секунды | сек→мин |
| Инфра | только Cursor | публичный HTTPS | 24/7 worker | adapter + Cursor |
| Сложность | низкая | средняя | средняя | высокая |
| Auth-риск | общий | общий | общий | общий |

**Рекомендация:** начать с **A**, после smoke-теста токена. Если понадобится real-time — добавить B/C как детектор, оставив approve/AI в Automation (D).

---

## 8. Чеклист перед реализацией агента

- [ ] Группа закрытая, заявки включены  
- [ ] Smoke-тест `getRequests` / `approveRequest` с выбранным токеном  
- [ ] Если user token: план refresh / мониторинг expiry  
- [ ] Если нужен scope `groups`: запрос в support / VK ID business (учесть риск отказа)  
- [ ] Repo по шаблону Cloud pipeline  
- [ ] Secrets в Cursor Dashboard  
- [ ] `APPROVE_ALLOW=no` на первом прогоне  
- [ ] Ledger + incident queue  
- [ ] Egress до `api.vk.com` в Cloud environment  

---

## 9. Ссылки (официальные)

- Методы groups: https://dev.vk.com/ru/method/groups  
- `groups.getRequests`: https://dev.vk.com/ru/method/groups.getRequests  
- `groups.approveRequest`: https://dev.vk.com/ru/method/groups.approveRequest  
- `groups.removeUser`: https://dev.vk.com/ru/method/groups.removeUser  
- Callback API: https://dev.vk.com/ru/api/callback/getting-started  
- Bots Long Poll: https://dev.vk.com/ru/api/bots-long-poll/getting-started  
- Схема событий (в т.ч. `join_type`): https://dev.vk.com/ru/api/community-events/json-schema  
- Ключ сообщества: https://dev.vk.com/ru/api/access-token/community-token  
- Права доступа: https://dev.vk.com/ru/reference/access-rights  
- Обзор токенов: https://dev.vk.com/ru/api/access-token/getting-started  

---

## 10. Следующий шаг

1. Провести smoke-тест токена на боевой/тестовой закрытой группе.  
2. Зафиксировать результат (community `manage` vs user `groups`) в `memory/` / issue.  
3. Только после PASS по auth — собирать pipeline агента по разделу 6.
