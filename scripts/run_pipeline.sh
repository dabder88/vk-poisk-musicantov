#!/usr/bin/env bash
# Run full VK join-request pipeline (dry-run by default).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RUN_ID="${1:-R-$(date -u +%Y%m%d-%H%M)}"
RUN_DIR="memory/runs/${RUN_ID}"

echo "=== VK Join Pipeline: ${RUN_ID} ==="

python3 scripts/doctor.py
python3 scripts/start_run.py --run-id "${RUN_ID}"
python3 scripts/fetch_requests.py --run-dir "${RUN_DIR}"
python3 scripts/decide.py --run-dir "${RUN_DIR}"
python3 scripts/approve.py --run-dir "${RUN_DIR}" --run-id "${RUN_ID}"
python3 scripts/validate_run.py --run-dir "${RUN_DIR}" -o "${RUN_DIR}/qa.json"

echo ""
echo "=== DONE ==="
echo "run_id: ${RUN_ID}"
echo "requests: $(python3 -c "import json; d=json.load(open('${RUN_DIR}/requests.json')); print(d.get('count',0))")"
echo "groups: $(python3 -c "import json; d=json.load(open('${RUN_DIR}/requests.json')); print(','.join(str(x) for x in d.get('group_ids',[])))")"
echo "to_approve: $(python3 -c "import json; d=json.load(open('${RUN_DIR}/decision.json')); print(len(d.get('to_approve',[])))")"
echo "qa: $(python3 -c "import json; print(json.load(open('${RUN_DIR}/qa.json'))['status'])")"
