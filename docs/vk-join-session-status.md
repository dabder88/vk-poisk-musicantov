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
5. Коммить файл вместе с кодом сессии. Не коммитить `memory/site.env.local`, `memory/local.env`, `.cursor/vk-join-handoff.md`, `memory/runs/*/`.

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
| Этап | **ПК: 162 заявки приняты** (`R20260826-1453`). Автоприём — Планировщик на этом ПК, не облако. |
| Цель продукта | По расписанию принимать заявки в закрытые группы ВК (`approve_all`). |
| Где мы сейчас | Человек подтвердил: все принялись. Dry-run и live на ПК зелёные. Облако d753: doctor FAIL error 5. Файл `memory/local.env` человек создал; скрипт его не всегда видел (имя/пустое поле) — донастройка Планировщика. |
| Последний live VK | 2026-08-26 ПК `R20260826-1453`: 71+29+62=162, qa PASS. Человек: «Все принялось». |
| Последний успешный полный dry-run | 2026-08-26 `R20260826-pc` ПК: 162, qa PASS, approved=0. Раньше облако 2026-08-25 `R20260825-1552`, 159. |
| Последняя сессия (облако) | 2026-08-26 `cursor/vk-join-dryrun-new-vm-d753`: doctor FAIL error 5. INC-1106 `needs-human`. |
| Open incidents | Нет `status: open`. Needs-human: INC-1106 (облако IP), INC-0836 (VM 39da `invalid_grant`). |
| Код брать с | Ветка **с кэшем**, не `main`. `cursor/vk-join-dryrun-new-vm-d753`. |
| Облако d753 / 39da | **Не** `doctor.py`, **не** `refresh force`, **не** Cursor Automation. |
| Паблики | `VK_GROUP_ID` CSV: `37759698`,`12830069`,`37636297`. `VK_GROUP_IDS` не задан. |
| ПК человека | `F:\ProjectsAI\vk-poisk-musicantov`, PowerShell. Кэш `memory/site.env.local`. Live прошёл. Дальше Планировщик + `run-live.ps1`. |

---

## Итог сессии 2026-08-26 (простыми словами)

Облако снова не смогло принять заявки: токен живой, но запросы уходят с разных IP (error 5). На **компьютере человека** тот же pipeline прошёл целиком.

| Прогон | Что вышло |
|--------|-----------|
| Облако 39da | doctor FAIL `invalid_grant`. Эту VM не использовать. |
| Облако d753 (Сессия 9) | refresh OK, потом error 5 на 2 из 3 групп. Fetch не было. |
| ПК doctor | PASS, три группы отвечают. |
| ПК dry-run `R20260826-pc` | 162 заявки, **никого не приняли** (проба). qa PASS. |
| ПК live `R20260826-1453` | 71+29+62=162, **человек подтвердил: все принялись**. qa PASS. |

Автоприём по расписанию — **Планировщик Windows на этом ПК**, не Cursor Automation в облаке.

Код: ветка `cursor/vk-join-dryrun-new-vm-d753` (с кэшем), не `main`. Одна команда на ПК: `scripts/run_once.py`. Для расписания: `scripts/run-live.ps1` + gitignored `memory/local.env`. `site.env.local` не трогать (кэш токена).

---

## Как запускать автоприём

Рабочая папка: `F:\ProjectsAI\vk-poisk-musicantov`. Консоль: **PowerShell** (не Git Bash). Ветка с кэшем, не `main`.

Два файла в `memory\` (оба **не** в git):

| Файл | Зачем | Трогать? |
|------|--------|----------|
| `site.env.local` | Кэш access/refresh после удачного doctor | Не удалять, не слать в чат |
| `local.env` | Группы + `VK_DEVICE_ID` + сервисный ключ для Планировщика | Создать рядом, не вместо кэша |

В `local.env` три строки `имя=значение` (без кавычек и пробелов вокруг `=`):

- группы — то же имя секрета, что в Dashboard, значение из таблицы «Какие паблики» (три числа через запятую);
- device id — с того же `finish`, что refresh;
- сервисный ключ приложения.

Пустое значение после `=` скрипт не подхватит. Файл не коммитить и не слать в чат.

Имя файла именно `local.env`, не `local.env.txt` (в проводнике включить расширения). Кодировка UTF-8 или Unicode.

### Вручную (сейчас)

Проба (никто не вступит):

```powershell
python scripts/run_once.py --count 200
```

Принять всех в очереди:

```powershell
python scripts/run_once.py --live --count 200
```

Если скрипт не видит группы — в том же окне сначала задай `VK_GROUP_ID` списком из таблицы пабликов (три числа через запятую, без пробелов), затем ту же команду `--live`.

`--count 200` — лимит ВК, больше нельзя. Doctor перед каждым прогоном **не** запускать, если кэш уже есть.

Если `local.env` подхватился, после `git pull` в начале будет строка `OK loaded local.env keys=...` (только имена ключей). Если `ERROR set VK_GROUP_ID` — задай `$env:VK_GROUP_ID` как в команде выше.

### По расписанию (Планировщик Windows)

1. `git pull origin cursor/vk-join-dryrun-new-vm-d753`
2. Есть оба файла: `memory\site.env.local` и `memory\local.env`.
3. Планировщик заданий → Создать задачу.
4. Триггер: каждые 30 или 60 минут.
5. Действие: программа `powershell.exe`
6. Аргументы:

```text
-NoProfile -ExecutionPolicy Bypass -File "F:\ProjectsAI\vk-poisk-musicantov\scripts\run-live.ps1"
```

7. Выполнять, когда пользователь вошёл в Windows. Спящий ПК заявки не примет.

Скрипт сам ставит live (`APPROVE_ALLOW=yes`, `DRY_RUN=no`) и `count=200`.

### Чего не делать

- Cursor Automation / новый Cloud Agent «на всякий случай».
- `doctor.py` в цикле и `get_vk_token.py refresh` «для проверки».
- `&&` в Windows PowerShell 5 (нужна `;` или отдельные строки).
- Коммитить `site.env.local` / `local.env` / токены в чат.
- Live в облаке, пока egress IP скачет.

---

## Проблемы этой сессии и как решили

| Симптом | Почему | Что сделали |
|---------|--------|-------------|
| Облако 39da: `invalid_grant` | Refresh в Dashboard уже использован / мёртвый | Не крутить doctor. INC-0836 needs-human. Новый вход VK на ПК (`start` → «Разрешить» → `finish`). |
| Облако d753: refresh OK, 2 группы error 5 | Токен к IP, облако ходит с разных адресов | Один extra refresh, стоп. INC-1106 needs-human (infra). Перешли на ПК. |
| «Какой новый ключ?» | Путаница: сервисный ключ приложения vs одноразовая пара refresh+device_id | Сервисный ключ не менять. `start`/`finish` — это вход в ВК на **этой** машине. |
| PowerShell: `&&` недопустим | Старый PowerShell не знает `&&` | Команды через `;` или по строкам. На Windows `python`, не `python3`. |
| Вставка превратилась в `\x3b` | Точка с запятой сломалась при копировании | Вставлять команды **по одной**. |
| `device_id is invalid`, длины 8 и 8 | В переменные попали обрезки, не полные строки с `finish` | Нужны длины примерно 200+ и десятки. Пара **с одного** `finish`. |
| Длины 0 | Закрыли окно PowerShell — `$env:...` стёрлись | Заново задать в **этом** окне или писать в `local.env`. |
| `count should be less or equal to 200` | `run_once` запросил 1000 | Никого не приняли. Повтор `--count 200`. В коде лимит 200. |
| `ERROR set VK_GROUP_ID` при `--live` | Новое окно / `local.env` не прочитался (пусто, `.txt`, не тот путь) | Задать список пабликов в этом окне (таблица выше) или починить `local.env`. Лоадер читает UTF-16 и `.txt`. |
| Пять команд вместо одной | Ручная проверка, чтобы не принять людей случайно | `python scripts/run_once.py --live --count 200`. Расписание: `run-live.ps1`. |
| Зачем облако, если ПК работает | Cursor Automation = облако; IP там не липкий | Автоприём на ПК. Облако не включать, пока IP не стабилен. |

Старые API-ошибки (5, 27, 15, кэш refresh) — таблица **«Ошибки и как чинили»** ниже.

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
- 2026-08-26 сессия d753 + ПК: облако doctor FAIL error 5; на ПК doctor PASS → dry-run 162 → live 162 принято. `run_once.py`, `run-live.ps1`, `memory/local.env`, лимит getRequests 200, doctor убран из snapshot `install`.

`main` **без** кэша снова делает refresh в каждом процессе и сжигает секрет. Не ветвиться от голого `origin/main`.

---

## Что сделали в этой сессии, зачем, выводы

**Зачем.** Принять заявки и понять, где может жить автоприём. Облако 39da мёртвое (`invalid_grant`). Новая VM d753 — проверка «вдруг IP повезёт». Параллельно человек на ПК.

**Облако d753.** Один doctor: refresh OK, extra refresh, 2/3 групп error 5. start_run не было. INC-1106. Fixer не крутил doctor: убрал `doctor.py` из `environment.json` install; hard-stop fixer на error 5 после extra refresh.

**ПК (итог, который нужен продукту).**

1. Doctor PASS по трём группам (после нормальных длин refresh/device_id).
2. Dry-run `R20260826-pc`: 162, approved=0, qa PASS.
3. Live `R20260826-1453`: 162, человек: все принялись. qa PASS.
4. Одна команда `run_once.py --live --count 200`. Расписание: Планировщик + `run-live.ps1` + `local.env`.

**Вывод.** Надёжный приём — ПК с одним IP и кэшем на диске. Облако Cursor для live/Automation пока лотерея (error 5). Код кэша/refresh заново не писать. `main` без кэша не использовать.

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
| Live `groups.approveRequest` на ПК | `R20260826-1453`: 162, qa PASS. Человек: все принялись |
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
| Live `groups.approveRequest` | Сделано на ПК `R20260826-1453`. Повтор сразу не нужен. Облако live не включать |
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
| `count` > 200 в getRequests | ВК error 100, 0 заявок | Лимит 200 в `run_once` / `fetch_requests`. Live повтор с `--count 200`. |
| `local.env` не подхватился | Не то имя, UTF-16, пустое значение групп | Лоадер: utf-8-sig/utf-16, `.txt`; в выводе `OK loaded ... keys=`. Запас: переменная групп в этом окне. |
| PowerShell `&&` / длины env 0 | Не bash; `$env:` живёт только в этом окне | `;` или отдельные строки; для расписания — файл `local.env`. |

---

## Следующий этап (человек + следующий агент)

### Человек

1. Автоприём: Планировщик Windows → `scripts/run-live.ps1`, оба файла в `memory\` (`site.env.local` + `local.env` с непустым `VK_GROUP_ID`).
2. Ручной приём: `python scripts/run_once.py --live --count 200` (группы из таблицы пабликов, если `local.env` не подхватился).
3. Облако и 39da/d753 для doctor/Automation не использовать.

### Следующий агент

Сначала этот файл (блоки «Итог сессии» и «Как запускать автоприём»). Live на ПК был. Не doctor на облаке. Не выдумывать повторный live.

---

## Какой результат хотим

**Ближайший:** донастроить Планировщик на ПК (файл `local.env` читается, задача тикает). Облако не автозапуск.

**Дальше:** live только после зелёного dry-run на той машине, где вызывают API; Automation на облаке — только понимая, что error 5 может повториться.

**Дальше:** тот же pipeline с `APPROVE_ALLOW=yes` и `DRY_RUN=no` (ставит человек), live approve, ledger, затем Automation по расписанию на той же схеме (кэш, один refresh на VM, копирование refresh между VM).

**Не цель этой фазы:** чинить sticky IP инфраструктуру Cursor; изобретать refresh/кэш заново; live «на всякий случай».

---

## Журнал сессий

### 2026-08-26 — docs — итог сессии + инструкция автоприёма
- В этот файл: итог простыми словами, как запускать вручную и Планировщиком, таблица проблем сессии.
- Человек: 162 приняты; `local.env` создал; скрипт его не всегда видел — в инструкции запас через `$env:VK_GROUP_ID`.

### 2026-08-26 — docs — автозапуск на ПК, не облако
- Человек: все 162 принялись. Дальше Планировщик Windows + `scripts/run-live.ps1` + gitignored `memory/local.env`.
- Cursor Automation на облаке не ставить: error 5.

### 2026-08-26 — R20260826-1453 — ПК, live PASS
- Человек: `run_once.py --live --count 200`. Кэш reuse, без doctor. `APPROVE_ALLOW=yes` `DRY_RUN=no`.
- fetch: 37759698=71, 12830069=29, 37636297=62, всего 162, errors=0.
- decide: to_approve=162 skip=0.
- approve: live path (from_cache), не dry-run. qa PASS errors=0. Строка `OK approved=` в чат не пришла.
- Первый `--live` с count=1000: error 100, 0 заявок, никого не приняли. Затем count=200.

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
