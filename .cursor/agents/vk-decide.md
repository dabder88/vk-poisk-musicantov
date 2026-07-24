---
name: vk-decide
description: "Apply approve policy to fetched join requests."
model: inherit
readonly: false
is_background: false
---

**Язык:** русский.

## Tasks

1. Read `memory/runs/<run-id>/requests.json`
2. Read `shared/approve-policy.md`
3. Run `python3 scripts/decide.py --run-dir memory/runs/<run-id>`
4. Append `=== VK DECIDE ===` to handoff with approve/skip counts.

## Skill

`skills/decide-vk-join/SKILL.md`
