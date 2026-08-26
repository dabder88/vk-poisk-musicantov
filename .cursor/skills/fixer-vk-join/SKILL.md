---
name: fixer-vk-join
description: Fix durable VK pipeline incidents.
---

# Fixer VK Join

## Steps

1. Read open incidents in `memory/pipeline-fix-queue.md`
2. **Hard stop (do not run doctor):**
   - `invalid_grant` / Dashboard refresh dead
   - **error 5 after one extra refresh** (infra / non-sticky Cloud Agent egress IP; same class as INC-0552)
   In both cases: do **not** run `doctor.py`. Do **not** call `refresh_from_env`, `force=True`, OAuth, getRequests, or approve. Do **not** invent refresh/cache again. Mark the incident `needs-human` and stop. Code cannot revive a dead Dashboard secret or pin Cloud Agent IP.
3. Otherwise: patch scripts/agents/skills/shared as needed
4. Run `python3 scripts/doctor.py` **only** if the incident is **not** about `invalid_grant` and **not** about error 5 after extra refresh
5. Update incident status (`fixed` or `needs-human`)

## Hard stop: `invalid_grant`

If doctor already failed with `invalid_grant` (`refresh_token is missing or invalid` / `already applied`) or the incident says Dashboard `VK_REFRESH_TOKEN` is dead:

- doctor and refresh are **forbidden**
- status = `needs-human`
- human hint without secrets: issue a new refresh (`python3 scripts/get_vk_token.py`, `docs/how-to-get-vk-user-token.md`) or copy a still-valid rotated token from a VM where exchange succeeded, then start a **new** VM

## Hard stop: error 5 after one extra refresh

If doctor already failed with **error 5 after one extra refresh** (retry-all already in code; sticky IP cannot be fixed here):

- doctor and refresh are **forbidden**
- status = `needs-human` (infra)
- human hint without secrets: dry-run on PC (one IP, disk cache). Copy rotated `VK_REFRESH_TOKEN` from gitignored `memory/site.env.local` of this VM into Dashboard **only if** another cloud run is actually needed. Do not print or commit the file. Do not spawn another Cloud VM «на всякий случай».
