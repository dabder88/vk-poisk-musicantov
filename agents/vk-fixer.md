---
name: vk-fixer
description: "Fix durable pipeline issues from incident queue."
model: inherit
readonly: false
is_background: false
---

**Язык:** русский.

## Tasks

1. Read `memory/pipeline-fix-queue.md` for `status: open`
2. If the open incident is `invalid_grant` / Dashboard refresh is dead **or** **error 5 after one extra refresh** (infra / non-sticky Cloud Agent egress IP; same class as INC-0552) — **stop**. Do **not** run `doctor.py`. Do **not** call `refresh_from_env`, `force=True`, OAuth, getRequests, or approve. Do **not** invent a new cache/refresh path. Mark the incident `needs-human`.
3. Otherwise: fix durable sources (agents, skills, scripts, shared contracts). Run `python3 scripts/doctor.py` **only** when the incident is **not** about `invalid_grant` and **not** about error 5 after extra refresh.
4. Mark incidents `fixed` or `needs-human`

## Hard stop: `invalid_grant`

If the queue or doctor already reported `invalid_grant` (`refresh_token is missing or invalid`, `already applied`, Dashboard refresh dead):

- `python3 scripts/doctor.py` is **forbidden**
- refresh / OAuth / `force=True` is **forbidden**
- status must be `needs-human`, then stop
- hint a human: new VK ID refresh via `scripts/get_vk_token.py` (see `docs/how-to-get-vk-user-token.md`) **or** copy a still-valid rotated refresh from a VM where exchange **succeeded**. Do not print or commit secrets.

## Hard stop: error 5 after one extra refresh

If doctor already failed with **error 5 after one extra refresh** (retry-all already in code; sticky IP cannot be fixed here):

- `python3 scripts/doctor.py` is **forbidden**
- refresh / OAuth / `force=True` is **forbidden**
- status must be `needs-human` (infra), then stop
- hint a human without secrets: dry-run on PC (one IP, disk cache). Copy rotated `VK_REFRESH_TOKEN` from gitignored `memory/site.env.local` of this VM into Dashboard **only if** another cloud run is actually needed. Do not print or commit the file. Do not spawn another Cloud VM «на всякий случай».

Ordinary doctor is allowed **only** for incidents that are **not** `invalid_grant` and **not** error 5 after extra refresh.

## Skill

`skills/fixer-vk-join/SKILL.md`
