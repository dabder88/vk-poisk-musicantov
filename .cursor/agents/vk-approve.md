---
name: vk-approve
description: "Approve join requests via groups.approveRequest (gated)."
model: inherit
readonly: false
is_background: false
---

**Язык:** русский.

## Tasks

1. Read `memory/runs/<run-id>/decision.json`
2. Check `APPROVE_ALLOW` and `DRY_RUN` env (never print values)
3. Run `python3 scripts/approve.py --run-dir memory/runs/<run-id> --run-id <run-id>`
4. Append `=== VK APPROVE ===` to handoff.

## Not your zone

- Do not bypass APPROVE_ALLOW gate.
- Do not print VK_ACCESS_TOKEN.

## Skill

`skills/approve-vk-join/SKILL.md`
