#!/usr/bin/env python3
"""Obtain VK user access token with groups scope via VK ID OAuth 2.1 + PKCE.

Usage:
  python3 scripts/get_vk_token.py start
  # open printed URL, allow access, copy redirect URL from browser
  python3 scripts/get_vk_token.py exchange --redirect-url 'http://localhost?code=...&device_id=...&state=...'

Environment (or CLI flags):
  VK_APP_ID          application client_id (required)
  VK_SERVICE_TOKEN   service token for confidential apps (required for exchange)
  VK_REDIRECT_URI    default: http://localhost
  VK_SCOPE           default: groups
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
SESSION_PATH = ROOT / "tmp" / "vk_oauth_session.json"
SESSIONS_PATH = ROOT / "tmp" / "vk_oauth_sessions.json"
AUTH_URL = "https://id.vk.ru/authorize"
TOKEN_URL = "https://id.vk.ru/oauth2/auth"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _random_string(length: int = 64) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _code_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return _b64url(digest)


def _save_session(data: dict[str, Any]) -> None:
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSION_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    history: dict[str, Any] = {}
    if SESSIONS_PATH.exists():
        history = json.loads(SESSIONS_PATH.read_text(encoding="utf-8"))
    history[data["state"]] = data
    SESSIONS_PATH.write_text(json.dumps(history, indent=2), encoding="utf-8")


def _load_session(state: str | None = None) -> dict[str, Any]:
    if state and SESSIONS_PATH.exists():
        history = json.loads(SESSIONS_PATH.read_text(encoding="utf-8"))
        if state in history:
            return history[state]

    if not SESSION_PATH.exists():
        raise SystemExit(
            f"Session file not found: {SESSION_PATH}\nRun: python3 scripts/get_vk_token.py start"
        )
    session = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
    if state and session.get("state") != state:
        raise SystemExit(
            f"state mismatch — no saved session for state={state}\n"
            "Open a fresh authorize link from: python3 scripts/get_vk_token.py start"
        )
    return session


def _build_authorize_url(
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
    code_challenge: str,
) -> str:
    from urllib.parse import urlencode

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "scope": scope,
        "prompt": "consent",
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def _parse_redirect_url(redirect_url: str) -> dict[str, str]:
    parsed = urlparse(redirect_url.strip())
    query = parse_qs(parsed.query)
    if parsed.fragment:
        fragment = parse_qs(parsed.fragment)
        for key, values in fragment.items():
            query.setdefault(key, values)

    def one(name: str) -> str:
        values = query.get(name, [])
        if not values:
            raise SystemExit(f"Missing '{name}' in redirect URL")
        return values[0]

    if query.get("error"):
        raise SystemExit(
            f"Authorization error: {query.get('error', [''])[0]} "
            f"{query.get('error_description', [''])[0]}"
        )

    return {
        "code": one("code"),
        "device_id": one("device_id"),
        "state": one("state"),
    }


def cmd_start(args: argparse.Namespace) -> int:
    client_id = args.client_id
    redirect_uri = args.redirect_uri
    scope = args.scope

    code_verifier = _random_string(64)
    state = _random_string(48)
    session = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "code_verifier": code_verifier,
        "state": state,
    }
    _save_session(session)

    url = _build_authorize_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=scope,
        state=state,
        code_challenge=_code_challenge(code_verifier),
    )

    print("1) Open this URL in a browser (logged in as group admin):")
    print(url)
    print()
    print("2) Allow access on the consent screen.")
    print("3) Browser will redirect to something like:")
    print(f"   {redirect_uri}?code=...&device_id=...&state=...")
    print("   Firefox may show «cannot connect to localhost» — THIS IS NORMAL.")
    print("   Copy the FULL URL from the address bar anyway.")
    print()
    print("   Easier: run on your PC:")
    print("   python3 scripts/get_vk_token.py listen")
    print()
    print("4) Exchange code for token:")
    print(
        "   python3 scripts/get_vk_token.py exchange "
        "--redirect-url '<paste full redirect URL>'"
    )
    print()
    print(f"Session saved to {SESSION_PATH}")
    return 0


def _exchange_token(
    session: dict[str, Any],
    redirect: dict[str, str],
    service_token: str,
) -> dict[str, Any]:
    if redirect["state"] != session["state"]:
        raise SystemExit("state mismatch — use redirect URL from the same auth session")

    if not service_token:
        raise SystemExit("VK_SERVICE_TOKEN is required for confidential app exchange")

    payload = {
        "grant_type": "authorization_code",
        "code_verifier": session["code_verifier"],
        "redirect_uri": session["redirect_uri"],
        "code": redirect["code"],
        "client_id": session["client_id"],
        "device_id": redirect["device_id"],
        "state": session["state"],
        "service_token": service_token,
    }

    response = requests.post(
        TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )

    try:
        body = response.json()
    except ValueError:
        raise SystemExit(f"Non-JSON response ({response.status_code}): {response.text[:500]}")

    if response.status_code != 200 or "error" in body:
        raise SystemExit(
            f"Token exchange failed ({response.status_code}): "
            f"{body.get('error', 'unknown')} — {body.get('error_description', body)}"
        )
    return body


def _print_token_result(body: dict[str, Any]) -> None:
    access_token = body["access_token"]
    refresh_token = body.get("refresh_token", "")
    expires_in = body.get("expires_in", "?")
    scope = body.get("scope", "")
    user_id = body.get("user_id", "?")

    out_path = ROOT / "tmp" / "vk_tokens.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(body, indent=2), encoding="utf-8")

    print("OK token received")
    print(f"user_id={user_id}")
    print(f"scope={scope}")
    print(f"expires_in={expires_in} seconds (~1 hour for access_token)")
    print()
    print("Put this value into Cursor Secret VK_ACCESS_TOKEN:")
    print(access_token)
    print()
    if refresh_token:
        print("Also save refresh_token securely (for renewal). Stored in:")
        print(out_path)
    print()
    print("Verify:")
    print("  export VK_ACCESS_TOKEN='...'")
    print("  export VK_GROUP_ID='...'")
    print("  python3 scripts/doctor.py")


def _redirect_parts(redirect_uri: str) -> tuple[str, int, str]:
    parsed = urlparse(redirect_uri)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    path = parsed.path or "/"
    return host, port, path


def cmd_listen(args: argparse.Namespace) -> int:
    """Start local server, open browser, auto-catch redirect."""
    client_id = args.client_id
    redirect_uri = args.redirect_uri
    scope = args.scope
    service_token = args.service_token

    code_verifier = _random_string(64)
    state = _random_string(48)
    session = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "code_verifier": code_verifier,
        "state": state,
    }
    _save_session(session)

    host, port, expected_path = _redirect_parts(redirect_uri)
    auth_url = _build_authorize_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=scope,
        state=state,
        code_challenge=_code_challenge(code_verifier),
    )

    result: dict[str, Any] = {"done": False}

    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *log_args: Any) -> None:
            return

        def do_GET(self) -> None:  # noqa: N802
            if self.path.split("?", 1)[0] != expected_path:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Not found")
                return

            full_url = f"{redirect_uri.split('?', 1)[0]}{self.path}"
            if "?" not in self.path:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing query parameters")
                return

            try:
                redirect = _parse_redirect_url(full_url)
                body = _exchange_token(session, redirect, service_token)
                result["done"] = True
                result["body"] = body
                html = (
                    "<html><body style='font-family:sans-serif;padding:2em'>"
                    "<h2>Готово</h2><p>Токен получен. Можно закрыть вкладку "
                    "и вернуться в терминал.</p></body></html>"
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
            except SystemExit as exc:
                msg = str(exc).encode("utf-8")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(msg)
                result["error"] = str(exc)
            finally:
                threading.Thread(target=server.shutdown, daemon=True).start()

    print("Запускаю локальный сервер для перехвата redirect...")
    print(f"Слушаю {host}:{port}{expected_path}")
    if port == 80:
        print("Нужны права на порт 80. Если ошибка — запустите с sudo или см. docs/ЧТО-ДЕЛАТЬ.md")
    print()
    print("Откроется браузер. Нажмите «Разрешить».")
    print("Страница localhost откроется нормально — код подхватится автоматически.")
    print()

    server = HTTPServer((host, port), CallbackHandler)
    threading.Timer(1.0, lambda: webbrowser.open(auth_url)).start()

    try:
        server.serve_forever()
    except OSError as exc:
        print(f"Не удалось запустить сервер на {host}:{port}: {exc}")
        print()
        print("Альтернатива: откройте ссылку вручную и скопируйте URL из адресной строки")
        print("(ошибка Firefox «не может подключиться» — это нормально, URL всё равно там):")
        print(auth_url)
        return 1

    if result.get("done"):
        print()
        _print_token_result(result["body"])
        return 0

    if result.get("error"):
        print(f"ERROR {result['error']}")
        return 1
    return 1


def cmd_exchange(args: argparse.Namespace) -> int:
    redirect = _parse_redirect_url(args.redirect_url)
    session = _load_session(state=redirect["state"])
    body = _exchange_token(session, redirect, args.service_token)
    _print_token_result(body)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VK ID OAuth 2.1 + PKCE helper")
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--client-id",
        default=os.environ.get("VK_APP_ID", "54693054").strip(),
        help="VK app client_id (env VK_APP_ID, default 54693054)",
    )
    common.add_argument(
        "--redirect-uri",
        default=os.environ.get("VK_REDIRECT_URI", "http://localhost").strip(),
        help="redirect_uri from app settings (env VK_REDIRECT_URI)",
    )
    common.add_argument(
        "--scope",
        default=os.environ.get("VK_SCOPE", "groups").strip(),
        help="requested scopes, space-separated (env VK_SCOPE)",
    )

    start = sub.add_parser("start", parents=[common], help="print authorize URL")
    start.set_defaults(func=cmd_start)

    exchange = sub.add_parser("exchange", parents=[common], help="exchange code for token")
    exchange.add_argument(
        "--redirect-url",
        required=True,
        help="full redirect URL from browser after consent",
    )
    exchange.add_argument(
        "--service-token",
        default=os.environ.get("VK_SERVICE_TOKEN", "").strip(),
        help="service token for confidential app (env VK_SERVICE_TOKEN)",
    )
    exchange.set_defaults(func=cmd_exchange)

    listen = sub.add_parser(
        "listen",
        parents=[common],
        help="local server catches redirect (run on your PC)",
    )
    listen.add_argument(
        "--service-token",
        default=os.environ.get("VK_SERVICE_TOKEN", "").strip(),
        help="service token for confidential app (env VK_SERVICE_TOKEN)",
    )
    listen.set_defaults(func=cmd_listen)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "start" and not args.client_id:
        parser.error("VK_APP_ID / --client-id is required")

    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
