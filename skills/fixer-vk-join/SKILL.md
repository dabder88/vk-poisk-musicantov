---
name: fixer-vk-join
description: Fix durable VK pipeline incidents.
---

# Fixer VK Join

## Steps

1. Read open incidents in `memory/pipeline-fix-queue.md`
2. **`invalid_grant` / Dashboard refresh dead:** do **not** run `doctor.py`. Do **not** call `refresh_from_env`, `force=True`, OAuth, getRequests, or approve. Do **not** invent refresh/cache again. Mark the incident `needs-human` and stop. Code cannot revive a dead Dashboard secret.
3. Otherwise: patch scripts/agents/skills/shared as needed
4. Run `python3 scripts/doctor.py` **only** if the incident is **not** about `invalid_grant`
5. Update incident status (`fixed` or `needs-human`)

## Hard stop

If doctor already failed with `invalid_grant` (`refresh_token is missing or invalid` / `already applied`) or the incident says Dashboard `VK_REFRESH_TOKEN` is dead:

- doctor and refresh are **forbidden**
- status = `needs-human`
- human hint without secrets: issue a new refresh (`python3 scripts/get_vk_token.py`, `docs/how-to-get-vk-user-token.md`) or copy a still-valid rotated token from a VM where exchange succeeded, then start a **new** VM
