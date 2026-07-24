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
2. Fix durable sources: agents, skills, scripts, shared contracts
3. Run `python3 scripts/doctor.py`
4. Mark incidents `fixed` or `needs-human`

## Skill

`skills/fixer-vk-join/SKILL.md`
