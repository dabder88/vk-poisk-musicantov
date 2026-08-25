# Как получить user token (VK ID) для Cloud Agent

Актуально на август 2026. Источники:
- [VK ID API: запрос кода и форма доступов](https://id.vk.ru/about/business/go/docs/ru/vkid/latest/vk-id/connection/api-description#Zapros-koda-podtverzhdeniya-i-rabota-s-formoj-razresheniya-dostupov-polzovatelya)
- [groups.getRequests](https://dev.vk.com/ru/method/groups.getRequests)

---

## Почему access_token с ПК не подходит для облака

`access_token` VK ID привязан к IP, с которого его **выдали**. Cloud Agent ходит с IP датацентра Cursor.

Если вызвать `api.vk.com` с другого IP:

```text
error 5 / subcode 1130
access_token was given to another ip address
```

**Ответ ТП VK (август 2026):** не использовать клиентский access_token с сервера. Перед вызовом API **обновить access_token через refresh_token там, где будете вызывать методы** — то есть на Cloud Agent.

Pipeline делает это в `VkClient.from_env()` через `scripts/vk_oauth.py`.

---

## Секреты в Cursor Dashboard

| Secret | Обязателен | Что это |
|--------|------------|---------|
| `VK_GROUP_ID` | да | ID группы без минуса |
| `VK_REFRESH_TOKEN` | да (для облака) | `refresh_token` из ответа `id.vk.ru/oauth2/auth` |
| `VK_DEVICE_ID` | да вместе с refresh | `device_id` из редиректа `http://localhost/?code=...&device_id=...` |
| `VK_SERVICE_TOKEN` | да для конфиденциального приложения | сервисный ключ из настроек VK ID |
| `VK_CLIENT_ID` | нет | по умолчанию `54693054` |
| `VK_ACCESS_TOKEN` | нет, если есть refresh | запасной access_token; на облаке всё равно будет refresh |

Не кладите **защищённый ключ** — pipeline его не использует.

---

## Шаг 1. Получить refresh_token (один раз, на ПК)

Нужны: приложение VK ID, scope `groups` (ТП уже выдаёт приложению), сервисный ключ.

```bash
export VK_SERVICE_TOKEN='сервисный_ключ'
python3 scripts/get_vk_token.py start
```

Откройте напечатанную ссылку `https://id.vk.ru/authorize?...&scope=groups&prompt=consent`.

После «Разрешить» адрес будет **не токен**, а код:

```text
http://localhost/?code=...&device_id=...&state=...
```

Обмен (на том же ПК, сразу):

```bash
python3 scripts/get_vk_token.py finish --redirect-url 'ВСТАВЬТЕ_URL'
```

Ответ обмена (JSON):

```json
{
  "refresh_token": "...",
  "access_token": "vk2.a....",
  "id_token": "...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "user_id": 4253689,
  "state": "...",
  "scope": "vkid.personal_info groups"
}
```

В `scope` обязательно должно быть `groups`.

Скрипт напечатает значения для Dashboard. **Не коммитьте их.**

---

## Шаг 2. Cloud Agent

На каждый run `doctor.py` / `fetch` / live `approve` вызывает:

```text
POST https://id.vk.ru/oauth2/auth
grant_type=refresh_token
refresh_token + device_id + client_id [+ service_token]
```

Новый `access_token` привязан к IP Cloud Agent → затем `groups.getRequests`.

Если VK **ротирует** `refresh_token`, обновите секрет `VK_REFRESH_TOKEN` в Dashboard до следующего запуска.

---

## Создание приложения VK ID (если ещё нет)

1. Кабинет: https://id.vk.ru/business/go (VK Бизнес ID).
2. Приложение Web, redirect `http://localhost`.
3. Scope `groups` — расширенный, через `devsupport@corp.vk.com`.
4. На авторизации запрашивать `scope=groups` и `prompt=consent` (права на приложении ≠ права в токене).

---

## Ошибки

| Код | Смысл | Действие |
|-----|--------|----------|
| 5 / 1130 | другой IP | `VK_REFRESH_TOKEN` + `VK_DEVICE_ID` на Cloud Agent |
| 10 | VK не может проверить токен | нет `groups` в scope при OAuth |
| 15 | нет прав / не админ | scope `groups`, админ группы |
| 27 | community token | нужен user token / refresh VK ID |

Ключ сообщества из «Работа с API → Ключи доступа» для заявок не подходит (error 27).
