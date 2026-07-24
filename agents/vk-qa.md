---
name: vk-qa
description: "Validate VK join pipeline run artifacts."
model: inherit
readonly: false
is_background: false
---

**Язык:** русский.

## Tasks

1. Run `python3 scripts/validate_run.py --run-dir memory/runs/<run-id> -o memory/runs/<run-id>/qa.json`
2. Append `=== VK QA ===` with verdict PASS/FAIL to handoff.

## Skill

`skills/qa-vk-join/SKILL.md`
