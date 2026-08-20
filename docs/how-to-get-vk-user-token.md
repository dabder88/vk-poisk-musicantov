# Как получить user token с правом `groups`

Поддержка VK подтвердила: права для приложения выданы. Чтобы они попали в токен, их нужно **запросить на шаге авторизации** — параметр `scope=groups` в OAuth VK ID.

Старый способ `oauth.vk.com/authorize?response_type=token` **больше не работает** (Implicit Flow отключён с 25.06.2024). Используйте **VK ID OAuth 2.1 + PKCE**.

Официальная документация: [Запрос кода подтверждения и форма разрешений](https://id.vk.ru/about/business/go/docs/ru/vkid/latest/vk-id/connection/api-description#Zapros-koda-podtverzhdeniya-i-rabota-s-formoj-razresheniya-dostupov-polzovatelya).

## Что понадобится

| Параметр | Где взять |
|----------|-----------|
| **client_id** (ID приложения) | Кабинет VK ID → ваше Standalone-приложение → «ID приложения» (у вас: `54693054`) |
| **redirect_uri** | В настройках приложения: `http://localhost` (должен совпадать **точно**) |
| **service_token** | Кабинет приложения → «Сервисный ключ доступа» (нужен при обмене кода на токен для конфиденциального приложения) |
| **scope** | `groups` — именно это право нужно для `groups.getRequests` и `groups.approveRequest` |

**Не путать:**
- **Ключ сообщества** («Работа с API → Ключи доступа») — для этого pipeline **не подходит** (ошибка 27).
- **Защищённый ключ** (client_secret) — для серверного OAuth, **не** вставлять в `VK_ACCESS_TOKEN`.
- **Сервисный ключ** — только для шага обмена кода, **не** в `VK_ACCESS_TOKEN`.

## Быстрый способ (скрипт в репозитории)

На своём компьютере (не в Cloud Agent):

```bash
cd vk-poisk-musicantov
python3 -m pip install -r requirements.txt

export VK_APP_ID=54693054
export VK_SERVICE_TOKEN='ваш_сервисный_ключ_из_кабинета'
export VK_REDIRECT_URI='http://localhost'
export VK_SCOPE='groups'

# Шаг 1: ссылка для входа
python3 scripts/get_vk_token.py start
```

1. Откройте напечатанную ссылку в браузере.
2. Войдите под аккаунтом **администратора группы**.
3. На форме разрешений подтвердите доступ (должен быть запрошен scope `groups`).
4. Браузер перенаправит на `http://localhost?code=...&device_id=...&state=...`  
   Страница может не открыться — это нормально. **Скопируйте полный URL из адресной строки.**

```bash
# Шаг 2: обмен кода на токен
python3 scripts/get_vk_token.py exchange \
  --redirect-url 'http://localhost?code=...&device_id=...&state=...'
```

Скрипт выведет `access_token`. Его нужно положить в **Cursor Secrets → `VK_ACCESS_TOKEN`**.

Проверка:

```bash
export VK_ACCESS_TOKEN='полученный_access_token'
export VK_GROUP_ID='ваш_id_группы'
python3 scripts/doctor.py
```

Ожидаемый результат: `OK VK API groups.getRequests reachable`.

## Ручной способ (без скрипта)

### 1. Сгенерировать PKCE

```python
import base64, hashlib, secrets
verifier = ''.join(secrets.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-') for _ in range(64))
challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
state = ''.join(secrets.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-') for _ in range(48))
print('code_verifier:', verifier)
print('code_challenge:', challenge)
print('state:', state)
```

Сохраните `code_verifier` и `state` — они понадобятся при обмене.

### 2. Открыть ссылку авторизации

Подставьте свои значения:

```
https://id.vk.ru/authorize?response_type=code&client_id=54693054&redirect_uri=http%3A%2F%2Flocalhost&state=ВАШ_STATE&code_challenge=ВАШ_CHALLENGE&code_challenge_method=S256&scope=groups&prompt=consent
```

### 3. Обменять code на токен

```bash
curl -X POST 'https://id.vk.ru/oauth2/auth' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=authorization_code' \
  -d 'code_verifier=ВАШ_CODE_VERIFIER' \
  -d 'redirect_uri=http://localhost' \
  -d 'code=КОД_ИЗ_REDIRECT' \
  -d 'client_id=54693054' \
  -d 'device_id=DEVICE_ID_ИЗ_REDIRECT' \
  -d 'state=ВАШ_STATE' \
  -d 'service_token=ВАШ_СЕРВИСНЫЙ_КЛЮЧ'
```

В ответе:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 3600,
  "scope": "groups ..."
}
```

`access_token` → в `VK_ACCESS_TOKEN`.  
`refresh_token` сохраните отдельно (срок жизни access_token ~1 час; для автоматизации позже можно добавить обновление).

## После получения токена

1. Обновите **Cursor Dashboard → Cloud Agents → Secrets**:
   - `VK_ACCESS_TOKEN` = новый user token
   - `VK_GROUP_ID` = без изменений
2. Запустите dry-run: `APPROVE_ALLOW=no`, `DRY_RUN=yes`
3. Если doctor и pipeline проходят — для реального приёма: `APPROVE_ALLOW=yes`, `DRY_RUN=no`

## Типичные ошибки

| Симптом | Причина | Решение |
|---------|---------|---------|
| `error 27` в doctor | Токен сообщества, не user | Получить user token через VK ID (эта инструкция) |
| `invalid_scope` | scope не выдан приложению | Написать в поддержку (у вас уже выдано — проверьте `scope=groups` в URL) |
| `state mismatch` | Другая сессия / другой redirect | Заново `get_vk_token.py start` и повторить обмен |
| Токен истёк через ~1 час | Нормально для VK ID | Обновить через `refresh_token` или пройти авторизацию снова |

## Ссылки

- [Справочник API VK ID](https://id.vk.ru/about/business/go/docs/ru/vkid/latest/vk-id/connection/api-description)
- [groups.getRequests](https://dev.vk.ru/ru/method/groups.getRequests)
- [Исследование по проекту](./vk-closed-group-join-requests.md)
