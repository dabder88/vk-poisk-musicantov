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

Скрипты — гейты (`scripts/doctor.py` и др.), не замена ролей (`run_pipeline.sh` не крутить вместо subagents).

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
| Этап | Код pipeline + кэш токена готовы. **Зелёный полный прогон на новой VM после копирования refresh в Dashboard — ещё нет.** |
| Цель продукта | По расписанию принимать заявки в закрытые группы ВК (`approve_all`). |
| Где мы сейчас | Проверка, что новый `VK_REFRESH_TOKEN` в Dashboard работает на **новой** Cloud VM. |
| Последний live VK | Нет. Approve только dry-run (или skipped). |
| Последний успешный полный dry-run | 2026-08-25, `run_id=R20260825-1552`, **другая** VM: 159 заявок, qa PASS, approved=0. |
| Последняя сессия (эта VM) | 2026-08-26: Dashboard-секрет **обменялся** (refresh OK, `scope=groups`). Doctor **FAIL** (error 5 на 2/3 групп). Fetch не стартовал. |
| Open incidents | Нет (все `status: fixed`). Infra error 5 может повториться. |
| Код брать с | Ветка **с кэшем**, не голый `origin/main`. Актуальная: `cursor/vk-join-dryrun-new-vm-2af9` (поверх `5563` + retry всех групп после extra refresh). Коммиты-ориентиры: `20fcc46` кэш, `3938aa8` fetch partial + extra refresh, `ac813db` retry all groups. |
| Эту VM | **Не** крутить `doctor.py` повторно и **не** `refresh force`. Кэш уже после extra refresh; ещё один exchange может сжечь Dashboard token. |
| Паблики | Три группы в секрете `VK_GROUP_ID` (CSV без пробелов; порядок `37759698`, `12830069`, `37636297`). `VK_GROUP_IDS` не задан. |

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
- Инциденты: INC-1526, INC-1545, INC-1552, INC-0552 — fixed (см. очередь).

`main` **без** кэша снова делает refresh в каждом процессе и сжигает секрет. Не ветвиться от голого `origin/main`.

---

## Что работает

| Что | Доказательство |
|-----|----------------|
| Обмен Dashboard `VK_REFRESH_TOKEN` на новой VM | 2026-08-26 doctor: refresh OK, `user_id=4253689`, `scope=groups`, не `invalid_grant` |
| Кэш после refresh | `memory/site.env.local` появляется, gitignored |
| Полный dry-run pipeline (старая VM) | R20260825-1552: fetch 70+28+61=159, decide 159, approve 159 dry_run, qa PASS |
| Multi-group parse + скрипты | юнит-тесты `tests/test_group_ids.py` и др. |
| Кэш / extra refresh / partial fetch | mock-тесты `tests/test_vk_oauth.py`, `tests/test_vk_ip_refresh.py` |

---

## Что не работает / не доказано

| Что | Статус |
|-----|--------|
| Doctor PASS по **всем трём** группам на **новой** VM (2026-08-26) | Нет: error 5 после extra refresh |
| Полный pipeline (fetch→qa) на новой VM после обновления секрета | Не запускался (gate doctor) |
| Live `groups.approveRequest` | Намеренно выкл. Не включать, пока нет qa PASS в dry-run на новой VM |
| Sticky egress IP Cloud Agent | Нет гарантии: токен привязан к IP выдачи, следующий HTTP может уйти с другого IP |
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

---

## Следующий этап (человек + следующий агент)

### Человек (до нового агента)

1. Скопировать `VK_REFRESH_TOKEN` из `memory/site.env.local` **VM от 2026-08-26** в Cursor Dashboard. Файл не печатать, не коммитить. `VK_DEVICE_ID` / `VK_SERVICE_TOKEN` не менять без причины.
2. Не включать live: не ставить одновременно `APPROVE_ALLOW=yes` и `DRY_RUN=no`.
3. Запускать следующего агента на ветке **с кэшем** (см. снимок), не на голом `main`.
4. Эту VM больше не использовать для doctor/refresh.

Зачем: VK ротирует refresh при обмене. Dashboard всё ещё может хранить **старый** refresh. Следующая **новая** VM должна получить уже ротированное значение, иначе `invalid_grant`.

### Следующий Director

1. Прочитать этот файл (снимок) и очередь инцидентов.
2. Env без печати значений: группы, refresh, device, service; зафиксировать `APPROVE_ALLOW` / `DRY_RUN` как yes/no/absent.
3. **Один** `python3 scripts/doctor.py`. PASS = refresh на **этой** новой VM + getRequests по каждой из трёх групп.
4. `invalid_grant` → needs-human, стоп. Error 5 после extra refresh → incident, **не** цикл doctor, fetch не стартовать.
5. PASS → `start_run` → subagents fetch → decide → approve → qa. Кэш; без второго exchange сразу.
6. Open incidents → `vk-fixer`.
7. Если VK снова ротировал refresh — hint человеку (копировать из **новой** VM в Dashboard до ещё одной VM).
8. **Обновить этот файл.**

Зачем: доказать зелёный dry-run на новой машине после обновления секрета. Без этого live по расписанию будет жечь токен или падать на IP.

---

## Какой результат хотим

**Ближайший (обязательный):** на **новой** VM, ветка с кэшем, секреты из Dashboard:

- один refresh, doctor PASS по 3 группам;
- fetch: заявки по каждой группе записаны;
- decide: `to_approve` = сумма (при `approve_all`);
- approve: **dry-run**, `approved=0`;
- `qa.json` PASS;
- в отчёте: `run_id`, `run_dir`, счётчики по группам, `approve=dry_run`;
- этот файл обновлён;
- человек снова копирует refresh в Dashboard, если был hint о ротации.

**Дальше:** тот же pipeline с `APPROVE_ALLOW=yes` и `DRY_RUN=no` (ставит человек), live approve, ledger, затем Automation по расписанию на той же схеме (кэш, один refresh на VM, копирование refresh между VM).

**Не цель этой фазы:** чинить sticky IP инфраструктуру Cursor; изобретать refresh/кэш заново; live «на всякий случай».

---

## Журнал сессий

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
