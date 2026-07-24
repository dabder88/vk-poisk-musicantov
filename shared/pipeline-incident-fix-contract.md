# Pipeline incident contract

## Format

```markdown
## INC-YYYYMMDD-HHMM-role-short-slug
status: open
run_date: YYYY-MM-DD
role: vk-agent
run_id: R001
severity: low | medium | high | blocker
category: prompt | script | docs | env | api | handoff | qa | approve | other

### What went wrong
- ...

### How the agent recovered this run
- ...

### Durable fix needed before next run
- ...

### Suggested files to inspect/change
- `path`

### Secrets
- none recorded

### Fixer resolution
- pending
```

## Categories for VK pipeline

- `api` — VK token invalid, error 15/27/103
- `env` — missing VK_GROUP_ID / VK_ACCESS_TOKEN
- `approve` — approveRequest failed
- `script` — gate script FAIL
