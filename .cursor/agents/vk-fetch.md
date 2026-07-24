---
name: vk-fetch
description: "Fetch pending VK group join requests via groups.getRequests."
model: inherit
readonly: false
is_background: false
---

**Язык:** русский.

## Tasks

1. Read `memory/runs/<run-id>/context.json`
2. Run `python3 scripts/fetch_requests.py --run-dir memory/runs/<run-id>`
3. Append `=== VK FETCH ===` block to handoff with count of requests.

## Not your zone

- Do not approve requests.
- Do not change policy.

## Skill

`skills/fetch-vk-join/SKILL.md`
