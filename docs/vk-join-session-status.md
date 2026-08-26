# VK Join pipeline — статус сессий

**Зачем файл:** следующий Cloud Agent / человек читает **этот документ первым** и понимает этап, не восстанавливая историю из чатов.

**Секреты:** не писать токены, содержимое `memory/site.env.local`, значения Dashboard. Только имена переменных и факты (present/absent, yes/no).

Смежные артефакты: инциденты — `memory/pipeline-fix-queue.md`; исследование — `docs/vk-closed-group-join-requests.md`; политика — `shared/approve-policy.md`; токен — `docs/how-to-get-vk-user-token.md`.

---

## Задача проекта (зачем агенты)

Закрытые сообщества ВКонтакте не пускают людей сразу: пользователь подаёт **заявку**, админ должен её принять. Вручную это не масштабируется (три паблика, десятки/сотни заявок).

**Итоговая задача:** по расписанию (Cursor Automation) **самим принимать заявки** на вступление в закрытые группы проекта через VK API: `groups.getRequests` → решение по политике (`approve_all`) → `groups.approveRequest`. Человек не сидит в очереди заявок. Live включают только явно (`APPROVE_ALLOW=yes` и `DRY_RUN=no`); по умолчанию dry-run.

**Проблема, которую решаем:**

1. Ключ сообщества (community token) для getRequests/approveRequest **не подходит** (error 27). Нужен **user token** админа с правом `groups`.
2. Клиентский `access_token`, полученный на ПК, **нельзя** дергать с Cloud Agent: другой IP → error 5. Нужен обмен `refresh_token` **на той же машине**, откуда идут вызовы API (см. ТП VK ниже).
3. Refresh одноразово ротируется. Повторный обмен без кэша сжигает секрет Dashboard (`invalid_grant`). На VM — кэш `memory/site.env.local`; между VM секрет копирует человек.
4. Cloud Agent — не вечный сервер и не Callback endpoint. Подходит **polling по расписанию**, не Long Poll.

**Роли агентов** (полный pipeline одним агентом нельзя; следующий этап только после PASS):

| Роль | Зачем |
|------|--------|
| Director (parent) | Оркестрация: `doctor` + `start_run`, затем subagents. Сам не fetch/decide/approve/qa. |
| `vk-fetch` | Снять очередь заявок по всем `group_ids`. |
| `vk-decide` | Применить `shared/approve-policy.md` (сейчас принять всех). |
| `vk-approve` | Одобрить (или dry-run) с гейтами. |
| `vk-qa` | Проверить артефакты прогона (`qa.json`). |
| `vk-fixer` | Только если в очереди `status: open`: починить код/контракт, не жечь refresh в цикле. |

Скрипты — гейты (`scripts/doctor.py` и др.), не замена ролей в облаке (`run_pipeline.sh` / `run_once.py` не крутить вместо subagents). На ПК человека `python scripts/run_once.py` (проба) и `--live` (принять).

---

## Какие паблики и как заданы в env

Принимаем заявки в **три** закрытых сообщества (числовые id **без минуса**):

| group_id | Порядок в CSV |
|----------|----------------|
| `37759698` | 1 |
| `12830069` | 2 |
| `37636297` | 3 |

**Как сейчас в Cursor Dashboard (проверено 2026-08-26):**

- Имя секрета: `VK_GROUP_ID` (не `VK_GROUP_IDS`).
- Формат: **один** CSV из трёх id, разделитель запятая, пробелов нет, порядок как в таблице (`37759698` затем `12830069` затем `37636297`).
- `VK_GROUP_IDS` **не задан** (`ABSENT`). Дублировать список туда не нужно.

Парсер `scripts/group_ids.py` читает оба имени: CSV / пробелы / `;`, минус в начале снимает. Список можно держать в `VK_GROUP_ID` **или** в `VK_GROUP_IDS` (или оба, unique с сохранением порядка). В `AGENTS.md` / README для нескольких пабликов часто пишут `VK_GROUP_IDS` — это рекомендация, не требование. Боевой конфиг уже в `VK_GROUP_ID`.

Один OAuth (refresh на хосте) на все три группы, где пользователь токена админ.

---

## Позиция ТП ВК (error 5 / другой IP)

Цитата ответа поддержки ВК (запрос про `User authorization failed: access_token was given to another IP address`, зафиксировано в этом файле 2026-08-26):

> Ошибка «User authorization failed: access_token was given to another IP address» возникает, если IP-адрес, с которого выполняется запрос, отличается от IP-адреса, с которого был получен токен.
>
> Например, это может произойти, если вы получаете клиентский токен, но используете его для вызова метода с сервера.
>
> Ошибку можно исправить, если перед вызовом метода обновить access token, используя refresh token в том месте, где планируете его использовать.

**Как это читаем для Cloud Agent:**

- Не брать `access_token` с ПК и не класть его в Dashboard как основной способ для API.
- На **каждой** новой VM один обмен refresh → access **на этом хосте**, затем вызовы `api.vk.com` с тем же кэшированным access (не новый exchange на каждый скрипт).
- Если после обмена на хосте часть запросов всё ещё error 5 — egress IP агента, скорее всего, **не sticky**: разные исходящие IP в одном прогоне. Один extra refresh допустим; цикл doctor/`force` — нет (сожжёт refresh). Это уже не «забыли refresh», а инфраструктура.

Практическая инструкция: `docs/how-to-get-vk-user-token.md`.

---

## Как обновлять (обязательно в конце каждой сессии)

1. Перепиши блок **«Снимок — читать первым»** под текущий факт (не оставляй устаревший PASS/FAIL).
2. Если менялось «работает / не работает» — поправь таблицы.
3. Новый прогон или инцидент — **добавь** запись в **«Журнал сессий»** (сверху журнала, новые выше). Старые записи не удаляй.
4. Обнови **«Следующий этап»** и дату `Обновлено`.
5. Коммить файл вместе с кодом сессии. Не коммитить `memory/site.env.local`, `.cursor/vk-join-handoff.md`, `memory/runs/*/`.

Шаблон журнала:

```markdown
### YYYY-MM-DD — <run_id или none> — <краткий итог>
- Агент / ветка / PR
- Env (флаги yes/no, без секретов)
- Doctor / fetch / decide / approve / qa
- Инциденты
- Код-фиксы
- Hint человеку
```

---

## Снимок — читать первым

| Поле | Значение |
|------|----------|
| Обновлено | 2026-08-26 |
| Этап | **ПК: полный dry-run PASS.** `run_id=R20260826-pc`, 162 заявки, никого не приняли. Live выкл. Облако не трогать. |
| Цель продукта | По расписанию принимать заявки в закрытые группы ВК (`approve_all`). |
| Где мы сейчас | ПК: fetch 71+29+62=162, decide 162, approve 162 dry_run, qa PASS. Live не было. Облако d753 по-прежнему FAIL (error 5). |
| Последний live VK | Нет. |
| Последний успешный полный dry-run | 2026-08-26, `run_id=R20260826-pc`, **ПК**: 71+29+62=162, qa PASS, approved=0. Раньше: 2026-08-25 `R20260825-1552` облако, 159. |
| Последняя сессия (облако) | 2026-08-26 `cursor/vk-join-dryrun-new-vm-d753`: doctor FAIL error 5. INC-1106 `needs-human`. |
| Open incidents | Нет `status: open`. Needs-human: INC-1106 (облако IP), INC-0836 (VM 39da `invalid_grant`). |
| Код брать с | Ветка **с кэшем**, не `main`. `cursor/vk-join-dryrun-new-vm-d753`. |
| Облако d753 / 39da | **Не** `doctor.py`, **не** `refresh force`. |
| Паблики | `VK_GROUP_ID` CSV: `37759698`,`12830069`,`37636297`. `VK_GROUP_IDS` не задан. |
| ПК человека | Полный dry-run PASS `R20260826-pc`. `APPROVE_ALLOW=no` `DRY_RUN=yes`. Doctor/refresh повторно не крутить. Live только если человек явно включит оба флага. |

---

## Что уже сделано (код и контракты)

- Pipeline ролей: Director только `doctor` + `start_run`, дальше subagents `vk-fetch` → `vk-decide` → `vk-approve` → `vk-qa` → `vk-fixer` при `status: open`.
- Три паблика в секрете `VK_GROUP_ID` одним CSV без пробелов, порядок `37759698` затем `12830069` затем `37636297`. `VK_GROUP_IDS` пустой. Парсер принимает CSV в `VK_GROUP_ID` или в `VK_GROUP_IDS`.
- VK ID: обмен `refresh_token` **на хосте агента** (`scripts/vk_oauth.py`), иначе error 5 (IP).
- Кэш на VM: gitignored `memory/site.env.local` (0600). `refresh_from_env()` без `force` — не больше одного HTTP exchange, дальше reuse.
- Error 5/1130: retry `getRequests` тем же токеном, затем **один** extra refresh (`force=True`), затем снова **все** группы (не только упавшие). Не цикл refresh.
- Fetch пишет `requests.json` даже при partial (пустые `user_ids` + `error_code`).
- Гейты approve: live только если `APPROVE_ALLOW=yes` **и** `DRY_RUN=no`. Иначе dry-run.
- Политика decide: `approve_all`.
- Инциденты: INC-1526, INC-1545, INC-1552, INC-0552 — fixed. INC-0836 — `needs-human` (`invalid_grant` на VM 39da). INC-1106 — `needs-human` (error 5 после extra refresh на VM d753, infra).
- 2026-08-26 сессия 39da: разобрали двухдневную путаницу «опять не тот токен»; человек обновил репо на ПК на ветку с кэшем.
- 2026-08-26 сессия d753: один doctor, refresh OK, extra refresh, 2/3 групп error 5. Из `install` в `.cursor/environment.json` убран `doctor.py`. Fixer: hard-stop на error 5 после extra refresh (как на `invalid_grant`).

`main` **без** кэша снова делает refresh в каждом процессе и сжигает секрет. Не ветвиться от голого `origin/main`.

---

## Что сделали в этой сессии, зачем, выводы

**Зачем сессия (d753 / Сессия 9).** Director: один doctor на **новой** Cloud VM (не 39da) после обновления репо на ПК. Не поднимать ещё одно облако «на всякий случай». Live не включать.

**Что сделали (облако d753).**

1. Прочитали этот файл целиком, очередь, ветка с кэшем (`…-39da`), не `main`. Это не VM 39da.
2. Env: три группы в `VK_GROUP_ID` (CSV совпал), `VK_GROUP_IDS` нет, refresh/device/service/access есть, `APPROVE_ALLOW`/`DRY_RUN` нет → только dry-run. Кэша на старте не было.
3. Один `python3 scripts/doctor.py`: refresh OK (`user_id=4253689`, `scope=groups`), кэш `memory/site.env.local` 0600. Extra refresh один раз. Затем `37759698` error 5, `12830069` error 5, `37636297` sample=1. FAIL errors=2. Повторный doctor не крутили.
4. start_run / fetch / decide / approve не стартовали (нет PASS).
5. INC-1106 `needs-human` (infra IP). Fixer: doctor/refresh **не** вызывал. Убрал `doctor.py` из `.cursor/environment.json` `install`. Hard-stop fixer на error 5 после extra refresh.
6. INC-0836 не трогали (`needs-human`, VM 39da). Секрет Dashboard на d753 **живой** (обмен прошёл) — это уже не `invalid_grant`.

**Почему два дня казалось «не тот токен».** Смешали две разные поломки:

| Что писало ВК | Что это по-человечески | Уже гоняли? |
|---------------|------------------------|-------------|
| `invalid_grant` | Одноразовый ключ уже использовали или в секреты попала неполная пара | Да: INC-1526 (второй doctor), эта VM 39da |
| error 5 | Ключ приняли, но запрос ушёл с другого адреса, не с того, где ключ выдали | Да: 26 авг другая VM после refresh OK; 25 авг fetch, потом extra refresh и PASS |

**Выводы (строго по тестам, без домыслов).**

- Копировать refresh с **живой** VM, где обмен только что прошёл и файл `memory/site.env.local` ещё есть — **работало** (INC-1545 → doctor PASS → R20260825-1552). `VK_DEVICE_ID` при таком копировании не меняют.
- Копировать со **уже мёртвой** VM / когда doctor уже сказал `invalid_grant` — нечего копировать. Нужен новый выпуск ключей на ПК (`get_vk_token.py start` + `finish`). Так было на 39da. На d753 обмен **удался** — для следующего облака копировать refresh с **этой** живой VM, не с 39da.
- Новый `finish` на ПК: в секреты кладут **оба** поля с этого раза (`VK_REFRESH_TOKEN` и `VK_DEVICE_ID`). Не access, не id. После `finish` ключ не «проверяют» — проверка сжигает.
- Облако Cursor не даёт 100%: 26 авг ключ был живой, три группы всё равно не прошли из‑за чужого IP. Полный dry-run на облаке один раз был (25 авг) — когда адрес случайно не скакал.
- Чтобы **наверняка** принять заявки: dry-run на своём ПК (один адрес, кэш на диске). Live не включать, пока dry-run на ПК не зелёный.
- Код кэша/refresh заново не писать. `main` без кэша не использовать.

---

## Что работает

| Что | Доказательство |
|-----|----------------|
| Doctor PASS по 3 группам **на ПК** (2026-08-26) | refresh OK `user_id=4253689` `scope=groups`; getRequests `37759698`/`12830069`/`37636297` sample=1; `SUMMARY errors=0` |
| Кэш после refresh (d753) | `memory/site.env.local` есть, mode 0600, gitignored |
| getRequests одна группа на d753 | `37636297` sample=1 |
| VM 39da (2026-08-26) | refresh **не** обменялся: `invalid_grant` (исторически) |
| Полный dry-run pipeline **на ПК** | `R20260826-pc`: fetch 71+29+62=162, decide 162, approve 162 dry_run, qa PASS, approved=0 |
| Multi-group parse + скрипты | юнит-тесты `tests/test_group_ids.py` и др. |
| Кэш / extra refresh / partial fetch | mock-тесты `tests/test_vk_oauth.py`, `tests/test_vk_ip_refresh.py` |

---

## Что не работает / не доказано

| Что | Статус |
|-----|--------|
| Doctor PASS по **всем трём** группам на **этой** VM (d753) | Нет: extra refresh, затем error 5 на `37759698` и `12830069` |
| Doctor PASS по 3 группам на VM 2af9 (2026-08-26) | Нет: refresh OK, затем error 5 после extra refresh |
| Doctor PASS на VM 39da | Нет: `invalid_grant`, getRequests не было |
| Полный pipeline (fetch→qa) **на ПК** | Да: `R20260826-pc` qa PASS, approve=dry_run, approved=0 |
| Live `groups.approveRequest` | Намеренно выкл. Можно включать только после этого PASS, явно `APPROVE_ALLOW=yes` и `DRY_RUN=no` на ПК |
| Sticky egress IP Cloud Agent | Нет: повтор 26 авг на двух новых VM (2af9 и d753) |
| Автокопирование ротированного refresh в Dashboard | Невозможно из агента. Нужен человек |

---

## Ошибки и как чинили

| Код / симптом | Смысл | Что делать / что уже сделано |
|---------------|--------|------------------------------|
| 5 / 1130 | `access_token` выдан другому IP | Сначала retry тем же токеном. Один extra refresh, если retry не помог. **Не** второй doctor сразу. Если после extra всё ещё 5 — **стоп** на этой VM (infra). |
| `invalid_grant` (already applied / missing or invalid) | Refresh уже использован или мёртвый | **Не чинить кодом.** Не крутить doctor. Incident `needs-human`. Человек: новый токен через `scripts/get_vk_token.py` **или** свежий refresh из `memory/site.env.local` **той** VM, где обмен ещё удался, в Dashboard. |
| 10 | Нет `groups` в scope | Не тот token / не тот обмен. Нужен user token с `scope=groups`. |
| 15 | Нет прав / не админ группы | Права админа на каждую группу. |
| 27 | Community (ключ сообщества) | Нужен **user** token, не ключ группы. |
| Refresh на каждый процесс | Doctor+fetch+approve жгли Dashboard token | Кэш `memory/site.env.local` (`20fcc46`). |
| Fetch abort, нет `requests.json` | Error 5 на 2-й группе ронял скрипт | Partial write + extra refresh (`3938aa8`). |
| Extra refresh ретраил только still_ip | Группа, ок на старом токене, не проверялась новым | Retry **всех** group_ids (`ac813db`). |
| `doctor.py` в `environment.json` install | Snapshot build менял refresh до Director | Убран из install (сессия d753). Doctor — gate, не setup. |

---

## Следующий этап (человек + следующий агент)

### Человек (live — только если сам решишь)

1. Dry-run на ПК уже зелёный. **Не** второй doctor. **Не** облако.
2. Реально принять заявки на ПК одной командой: `python scripts/run_once.py --live` (нужен `VK_GROUP_ID` и кэш `memory/site.env.local`). Без `--live` снова только проба. Cloud Director этот скрипт не использует.
3. Облако d753 / 39da не трогать. Automation на облаке — error 5 может повториться.
4. Ротированный refresh — в `memory/site.env.local` на ПК. Не печатать, не коммитить.

### Следующий агент

Сначала этот файл. На ПК dry-run `R20260826-pc` PASS. Live не выдумывать. Не doctor на облаке.

---

## Какой результат хотим

**Ближайший:** live на ПК только если человек явно включит `APPROVE_ALLOW=yes` и `DRY_RUN=no`. Иначе стоп: dry-run уже зелёный.

**Дальше:** live только после зелёного dry-run на той машине, где вызывают API; Automation на облаке — только понимая, что error 5 может повториться.

**Дальше:** тот же pipeline с `APPROVE_ALLOW=yes` и `DRY_RUN=no` (ставит человек), live approve, ledger, затем Automation по расписанию на той же схеме (кэш, один refresh на VM, копирование refresh между VM).

**Не цель этой фазы:** чинить sticky IP инфраструктуру Cursor; изобретать refresh/кэш заново; live «на всякий случай».

---

## Журнал сессий

### 2026-08-26 — R20260826-pc — ПК, полный dry-run PASS
- Человек, PowerShell. Кэш reuse, без второго refresh. `APPROVE_ALLOW=no` `DRY_RUN=yes`.
- fetch: 37759698=71, 12830069=29, 37636297=62, всего 162, errors=0.
- decide: to_approve=162 skip=0 mode=approve_all.
- approve: 162 dry_run, approved=0.
- qa: PASS errors=0.
- Live не было. Облако не трогали.

### 2026-08-26 — run_id none — ПК, doctor PASS по 3 группам
- Человек, PowerShell, `F:\ProjectsAI\vk-poisk-musicantov`. Длины refresh=262 device_id=86. Не облако.
- Один `python scripts/doctor.py`: refresh OK `user_id=4253689` `scope=groups`; getRequests OK `37759698`/`12830069`/`37636297` sample=1; `SUMMARY errors=0`.
- Fetch/decide/approve на ПК ещё нет. Live нет. `APPROVE_ALLOW=no` `DRY_RUN=yes`.
- Hint: не второй doctor; то же окно; дальше start_run+pipeline dry-run.

### 2026-08-26 — run_id none — VM d753, refresh OK, doctor FAIL error 5 после extra refresh
- Агент / ветка: Сессия 9 `bc-…d753`, `cursor/vk-join-dryrun-new-vm-d753` от `…-39da`. Не VM 39da.
- Env: `VK_GROUP_ID` present (3 id), `VK_GROUP_IDS` absent, refresh/device/service/access present. `APPROVE_ALLOW`/`DRY_RUN` absent → dry-run. Кэша на старте не было.
- Doctor **один раз**: refresh OK `user_id=4253689` `scope=groups`; extra refresh; `37759698` error 5; `12830069` error 5; `37636297` sample=1. FAIL. start_run/fetch/decide/approve не было. Повторный doctor не крутили.
- Approve: skipped (нет PASS). qa: нет. Live не было.
- INC-1106 `needs-human` (infra IP). Fixer: doctor/refresh не вызывал. Убран `doctor.py` из `.cursor/environment.json` install. Hard-stop fixer на error 5 после extra refresh.
- INC-0836 не меняли. Dashboard refresh на d753 живой (в отличие от 39da).
- Hint: dry-run на ПК. Эту VM не doctor. Не новое облако. Ротированный refresh — в gitignored `memory/site.env.local` этой VM (не печатать, не коммитить); в Dashboard копировать только если снова нужно облако.

### 2026-08-26 — docs — выводы сессии 39da + человек обновил репо на ПК
- Зачем: зафиксировать, что сделали, почему путались два дня, какие выводы по тестам (не домыслы).
- Облако: doctor один раз `invalid_grant`; fetch не было; INC-0836 needs-human.
- Поправка: копирование refresh с **живой** VM работало (25 авг). С мёртвой / после `invalid_grant` — нет. 100% на Cloud Agent нет (26 авг error 5 при живом токене).
- Человек: репозиторий на компьютере обновлён, ветка с кэшем. Дальше ключи и doctor на ПК.
- Этот файл — вход для следующего агента.

### 2026-08-26 — run_id none — эта VM, invalid_grant, копирование со старой VM провалилось
- Ветка: `cursor/vk-join-dryrun-new-vm-39da` от `cursor/vk-join-dryrun-new-vm-2af9`.
- Env: `VK_GROUP_ID` present (3 id), `VK_GROUP_IDS` absent, refresh/device/service present. `APPROVE_ALLOW`/`DRY_RUN` absent → dry-run. Кэша на старте не было.
- Doctor **один раз**: FAIL `invalid_grant: refresh_token is missing or invalid`. getRequests не было. `memory/site.env.local` так и нет.
- start_run/fetch/decide/approve не стартовали. Повторный doctor не крутили.
- INC-20260826-0836 `needs-human`. Fixer: в agent/skill запрет doctor при `invalid_grant`.
- Вывод: не копировать refresh с мёртвых Cloud VM. Нужна новая пара refresh+device_id с ПК. Error 5 на прошлой VM — это IP, не «не тот токен».

### 2026-08-26 — docs — три паблика в VK_GROUP_ID

- Зафиксировано: три group_id `37759698`, `12830069`, `37636297`.
- В Dashboard они лежат в `VK_GROUP_ID` как CSV без пробелов (не в `VK_GROUP_IDS`). Парсер это умеет.

### 2026-08-26 — docs — миссия проекта + цитата ТП ВК

- В `docs/vk-join-session-status.md`: зачем агенты, итоговая задача, проблема (заявки + IP/token).
- Полная цитата ТП ВК про error 5 (токен с одного IP, вызов с другого; refresh там, где вызываете API). Дубль в `docs/how-to-get-vk-user-token.md`.

### 2026-08-26 — run_id none — новая VM, секрет подхватился, doctor FAIL (error 5)

- Ветка: `cursor/vk-join-dryrun-new-vm-2af9` от `cursor/vk-join-dryrun-director-5563`.
- Env: `VK_GROUP_ID` present (3 id), `VK_GROUP_IDS` absent, refresh/device/service present. `APPROVE_ALLOW`/`DRY_RUN` absent → dry-run.
- Кэша на старте не было (норма для новой VM).
- Doctor **один раз**: refresh OK `user_id=4253689` `scope=groups`; extra refresh; `37759698` error 5; `12830069` sample=1; `37636297` error 5. FAIL. start_run/fetch не было.
- Fixer: INC-0552 fixed (retry all groups). Doctor повторно не гоняли. Cache-only probe: error 5 на всех 3 группах.
- Hint: скопировать `VK_REFRESH_TOKEN` из `memory/site.env.local` этой VM в Dashboard до следующей VM.

### 2026-08-25 — R20260825-1552 — полный dry-run на предыдущей VM

- Director: doctor PASS (refresh + getRequests по 3 группам; extra refresh на error 5 у части групп).
- Первый vk-fetch FAIL: error 5 на 2-й группе, `requests.json` не записан → INC-1552.
- Fixer: partial fetch + один extra refresh.
- Повторный fetch PASS from_cache: 37759698=70, 12830069=28, 37636297=61, всего 159.
- decide: to_approve=159, skip=0. approve: 159 dry_run, approved=0. qa PASS.
- INC-1526 (кэш), INC-1545 (сожжённый Dashboard refresh, затем секрет обновили) — fixed.

### Ранее (до кэша)

- Multi-group, VK ID refresh на хосте.
- Без кэша повторный doctor/`from_env` → `invalid_grant`. Код кэша обязателен.
