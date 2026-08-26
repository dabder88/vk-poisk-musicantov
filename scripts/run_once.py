#!/usr/bin/env python3
"""One-command local pipeline (PC). Cloud Director still uses subagents, not this.

Dry-run by default. Pass --live only to call groups.approveRequest.
Does not run doctor (reuse memory/site.env.local on this machine).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LOCAL_ENV = ROOT / "memory" / "local.env"


def load_local_env(path: Path = LOCAL_ENV) -> None:
    """Load gitignored memory/local.env into os.environ (do not overwrite set vars)."""
    if not path.is_file():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and not os.environ.get(key, "").strip():
            os.environ[key] = value


def run(script: str, extra: list[str]) -> None:
    cmd = [sys.executable, str(ROOT / "scripts" / script), *extra]
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Really approve (sets APPROVE_ALLOW=yes DRY_RUN=no for this process)",
    )
    parser.add_argument("--run-id", default="")
    parser.add_argument(
        "--count",
        type=int,
        default=200,
        help="Max getRequests per group (VK max 200)",
    )
    args = parser.parse_args()

    os.chdir(ROOT)
    load_local_env()

    if args.count > 200:
        print("WARN VK getRequests count max is 200; using 200")
        args.count = 200
    if args.count < 1:
        print("ERROR --count must be 1..200")
        return 1

    if args.live:
        os.environ["APPROVE_ALLOW"] = "yes"
        os.environ["DRY_RUN"] = "no"
        print("LIVE: groups.approveRequest will run")
    else:
        os.environ["APPROVE_ALLOW"] = os.environ.get("APPROVE_ALLOW", "no") or "no"
        os.environ["DRY_RUN"] = os.environ.get("DRY_RUN", "yes") or "yes"
        print("DRY-RUN: nobody will be approved")

    try:
        from scripts.group_ids import parse_group_ids

        parse_group_ids()
    except ValueError as exc:
        print(f"ERROR {exc}")
        print("Set VK_GROUP_ID (CSV of numeric ids) in this window first.")
        return 1

    run_id = args.run_id.strip() or datetime.now(timezone.utc).strftime("R%Y%m%d-%H%M")
    run_dir = f"memory/runs/{run_id}"
    print(f"run_id={run_id} approve_allow={os.environ['APPROVE_ALLOW']} dry_run={os.environ['DRY_RUN']}")

    run("start_run.py", ["--run-id", run_id])
    run("fetch_requests.py", ["--run-dir", run_dir, "--count", str(args.count)])
    run("decide.py", ["--run-dir", run_dir])
    run("approve.py", ["--run-dir", run_dir, "--run-id", run_id])
    run("validate_run.py", ["--run-dir", run_dir, "-o", f"{run_dir}/qa.json"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
