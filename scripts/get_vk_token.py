#!/usr/bin/env python3
"""Local VK ID OAuth helper (PKCE). Run on your PC, not in Cloud Agent.

start  — print authorize URL (save pending PKCE to gitignored file)
finish — exchange redirect URL for tokens; print Dashboard secrets
refresh — exchange VK_REFRESH_TOKEN on THIS host (Cloud Agent IP bind)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.vk_oauth import (  # noqa: E402
    DEFAULT_CLIENT_ID,
    DEFAULT_REDIRECT_URI,
    authorize_url,
    exchange_code,
    generate_pkce,
    public_token_meta,
    refresh_from_env,
)

PENDING_PATH = ROOT / "memory" / "vk-oauth-pending.json"


def cmd_start(args: argparse.Namespace) -> int:
    pkce = generate_pkce()
    client_id = args.client_id or os.environ.get("VK_CLIENT_ID", DEFAULT_CLIENT_ID)
    url = authorize_url(
        client_id=client_id,
        redirect_uri=args.redirect_uri,
        code_challenge=pkce["code_challenge"],
        state=pkce["state"],
        scope=args.scope,
    )
    PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
    PENDING_PATH.write_text(
        json.dumps(
            {
                "code_verifier": pkce["code_verifier"],
                "state": pkce["state"],
                "redirect_uri": args.redirect_uri,
                "client_id": client_id,
                "authorize_url": url,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(url)
    print(f"# PKCE saved to {PENDING_PATH} (gitignored). Do not commit.")
    return 0


def cmd_finish(args: argparse.Namespace) -> int:
    pending = json.loads(PENDING_PATH.read_text(encoding="utf-8"))
    qs = parse_qs(urlparse(args.redirect_url).query)
    code = (qs.get("code") or [""])[0]
    device_id = (qs.get("device_id") or [""])[0]
    state = (qs.get("state") or [""])[0]
    if not code or not device_id:
        print("ERROR redirect URL must contain code and device_id")
        return 1
    if state != pending["state"]:
        print("ERROR state mismatch")
        return 1

    service_token = os.environ.get("VK_SERVICE_TOKEN", "").strip() or None
    tokens = exchange_code(
        code=code,
        code_verifier=pending["code_verifier"],
        device_id=device_id,
        state=state,
        client_id=pending["client_id"],
        redirect_uri=pending["redirect_uri"],
        service_token=service_token,
    )
    meta = public_token_meta(tokens)
    print("OK exchanged code -> tokens")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print("")
    print("Put these in Cursor Dashboard → Secrets (do not commit):")
    print(f"VK_CLIENT_ID={pending['client_id']}")
    print(f"VK_DEVICE_ID={device_id}")
    print(f"VK_REFRESH_TOKEN={tokens.get('refresh_token', '')}")
    print(f"VK_ACCESS_TOKEN={tokens.get('access_token', '')}")
    print("VK_GROUP_ID=<без изменений>")
    return 0


def cmd_refresh(_args: argparse.Namespace) -> int:
    tokens = refresh_from_env(force=True)
    print("OK refresh_token exchanged on this host")
    print(json.dumps(public_token_meta(tokens), ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start", help="Print VK ID authorize URL")
    p_start.add_argument("--client-id", default="")
    p_start.add_argument("--redirect-uri", default=DEFAULT_REDIRECT_URI)
    p_start.add_argument("--scope", default="groups")
    p_start.set_defaults(func=cmd_start)

    p_finish = sub.add_parser("finish", help="Exchange redirect URL for tokens")
    p_finish.add_argument("--redirect-url", required=True)
    p_finish.set_defaults(func=cmd_finish)

    p_refresh = sub.add_parser("refresh", help="Refresh access_token on this host")
    p_refresh.set_defaults(func=cmd_refresh)

    args = parser.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
