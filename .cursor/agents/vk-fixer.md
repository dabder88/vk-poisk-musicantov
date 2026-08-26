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
2. If the open incident is `invalid_grant` / Dashboard refresh is dead — **stop**. Do **not** run `doctor.py`. Do **not** call `refresh_from_env`, `force=True`, OAuth, getRequests, or approve. Do **not** invent a new cache/refresh path. Mark the incident `needs-human` (code cannot revive a dead Dashboard secret).
3. Otherwise: fix durable sources (agents, skills, scripts, shared contracts). Run `python3 scripts/doctor.py` **only** when the incident is **not** about `invalid_grant`.
4. Mark incidents `fixed` or `needs-human`

## Hard stop: `invalid_grant`

If the queue or doctor already reported `invalid_grant` (`refresh_token is missing or invalid`, `already applied`, Dashboard refresh dead):

- `python3 scripts/doctor.py` is **forbidden**
- refresh / OAuth / `force=True` is **forbidden**
- status must be `needs-human`, then stop
- hint a human: new VK ID refresh via `scripts/get_vk_token.py` (see `docs/how-to-get-vk-user-token.md`) **or** copy a still-valid rotated refresh from a VM where exchange **succeeded**. Do not print or commit secrets.

Ordinary doctor is allowed **only** for incidents that are **not** `invalid_grant`.

## Skill

`skills/fixer-vk-join/SKILL.md`
