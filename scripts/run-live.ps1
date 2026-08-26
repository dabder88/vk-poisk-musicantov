# Run live join-approve on this PC (Windows Task Scheduler).
# Requires memory/local.env (group ids + device_id + service token)
# and memory/site.env.local (token cache after a successful doctor).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
python scripts/run_once.py --live --count 200
exit $LASTEXITCODE
