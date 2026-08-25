"""VK ID OAuth helpers: PKCE authorize URL and refresh_token exchange.

Cloud Agent must exchange refresh_token on the same host that calls api.vk.com
(VK error 5 / subcode 1130: access_token was given to another ip address).
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import string
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

VK_ID_AUTHORIZE = "https://id.vk.ru/authorize"
VK_ID_TOKEN = "https://id.vk.ru/oauth2/auth"
DEFAULT_CLIENT_ID = "54693054"
DEFAULT_REDIRECT_URI = "http://localhost"
DEFAULT_SCOPE = "groups"
ROTATED_REFRESH_HINT = (
    "WARN VK may have rotated refresh_token. Update Cursor Secret "
    "VK_REFRESH_TOKEN from gitignored memory/site.env.local on this VM "
    "before the next Cloud Agent. Do not commit the file. Do not print tokens."
)


class VkOAuthError(Exception):
    def __init__(self, error: str, description: str = "") -> None:
        self.error = error
        self.description = description
        super().__init__(f"VK ID OAuth error {error}: {description}".strip())


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def generate_pkce() -> dict[str, str]:
    verifier = _b64url(secrets.token_bytes(32))
    while len(verifier) < 43:
        verifier = _b64url(secrets.token_bytes(32))
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    alphabet = string.ascii_letters + string.digits + "_-"
    state = "".join(secrets.choice(alphabet) for _ in range(43))
    return {"code_verifier": verifier, "code_challenge": challenge, "state": state}


def authorize_url(
    *,
    client_id: str = DEFAULT_CLIENT_ID,
    redirect_uri: str = DEFAULT_REDIRECT_URI,
    code_challenge: str,
    state: str,
    scope: str = DEFAULT_SCOPE,
    prompt: str = "consent",
) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "scope": scope,
            "prompt": prompt,
        }
    )
    return f"{VK_ID_AUTHORIZE}?{query}"


def _post_token(payload: dict[str, str]) -> dict[str, Any]:
    response = requests.post(
        VK_ID_TOKEN,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    if "error" in body:
        raise VkOAuthError(
            str(body.get("error", "unknown")),
            str(body.get("error_description", "")),
        )
    if not body.get("access_token"):
        raise VkOAuthError("missing_access_token", "response has no access_token")
    return body


def exchange_code(
    *,
    code: str,
    code_verifier: str,
    device_id: str,
    state: str,
    client_id: str = DEFAULT_CLIENT_ID,
    redirect_uri: str = DEFAULT_REDIRECT_URI,
    service_token: str | None = None,
) -> dict[str, Any]:
    payload = {
        "grant_type": "authorization_code",
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
        "code": code,
        "client_id": client_id,
        "device_id": device_id,
        "state": state,
    }
    if service_token:
        payload["service_token"] = service_token
    return _post_token(payload)


def refresh_access_token(
    *,
    refresh_token: str,
    device_id: str,
    client_id: str = DEFAULT_CLIENT_ID,
    service_token: str | None = None,
    state: str | None = None,
    scope: str = DEFAULT_SCOPE,
) -> dict[str, Any]:
    """Exchange refresh_token for a new access_token bound to this host's IP."""
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "device_id": device_id,
        "scope": scope,
    }
    if service_token:
        payload["service_token"] = service_token
    if state:
        payload["state"] = state
    return _post_token(payload)


def public_token_meta(tokens: dict[str, Any]) -> dict[str, Any]:
    """Safe subset for logs (no secrets)."""
    access = str(tokens.get("access_token") or "")
    refresh = str(tokens.get("refresh_token") or "")
    return {
        "user_id": tokens.get("user_id"),
        "scope": tokens.get("scope"),
        "expires_in": tokens.get("expires_in"),
        "token_type": tokens.get("token_type"),
        "access_token_len": len(access),
        "refresh_token_present": bool(refresh),
    }


def token_cache_path() -> Path:
    override = os.environ.get("VK_TOKEN_CACHE_PATH", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[1] / "memory" / "site.env.local"


def _parse_env_file(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def load_token_cache(path: Path | None = None) -> dict[str, str]:
    target = path or token_cache_path()
    if not target.is_file():
        return {}
    try:
        return _parse_env_file(target.read_text(encoding="utf-8"))
    except OSError:
        return {}


def save_token_cache(tokens: dict[str, Any], path: Path | None = None) -> Path:
    """Persist host-bound tokens as env (mode 0600). Never log values."""
    target = path or token_cache_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = load_token_cache(target)
    access = str(tokens.get("access_token") or existing.get("VK_ACCESS_TOKEN") or "").strip()
    refresh = str(tokens.get("refresh_token") or existing.get("VK_REFRESH_TOKEN") or "").strip()
    user_id = tokens.get("user_id", existing.get("VK_TOKEN_USER_ID", ""))
    scope = tokens.get("scope", existing.get("VK_TOKEN_SCOPE", ""))
    expires_in = tokens.get("expires_in", existing.get("VK_TOKEN_EXPIRES_IN", ""))
    lines = [
        "# Host-bound VK tokens for this VM. Gitignored. Do not commit.",
        f"VK_ACCESS_TOKEN={access}",
        f"VK_REFRESH_TOKEN={refresh}",
        f"VK_TOKEN_USER_ID={user_id}",
        f"VK_TOKEN_SCOPE={scope}",
        f"VK_TOKEN_EXPIRES_IN={expires_in}",
        f"VK_TOKEN_CACHED_AT={int(time.time())}",
    ]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(target, 0o600)
    return target


def cached_tokens_as_oauth(cached: dict[str, str]) -> dict[str, Any] | None:
    access = cached.get("VK_ACCESS_TOKEN", "").strip()
    if not access:
        return None
    user_raw = str(cached.get("VK_TOKEN_USER_ID") or "").strip()
    user_id: Any = user_raw
    if user_raw.isdigit():
        user_id = int(user_raw)
    expires_raw = str(cached.get("VK_TOKEN_EXPIRES_IN") or "").strip()
    expires_in: Any = expires_raw
    if expires_raw.isdigit():
        expires_in = int(expires_raw)
    return {
        "access_token": access,
        "refresh_token": cached.get("VK_REFRESH_TOKEN", "").strip(),
        "user_id": user_id or None,
        "scope": cached.get("VK_TOKEN_SCOPE") or None,
        "expires_in": expires_in or None,
        "token_type": "Bearer",
        "from_cache": True,
    }


def refresh_from_env(*, force: bool = False) -> dict[str, Any]:
    """Exchange refresh_token at most once per VM; later processes reuse cache."""
    cache_path = token_cache_path()
    cached = load_token_cache(cache_path)
    if not force:
        reused = cached_tokens_as_oauth(cached)
        if reused:
            os.environ["VK_ACCESS_TOKEN"] = str(reused["access_token"])
            return reused

    refresh_token = (
        cached.get("VK_REFRESH_TOKEN", "").strip()
        or os.environ.get("VK_REFRESH_TOKEN", "").strip()
    )
    device_id = os.environ.get("VK_DEVICE_ID", "").strip()
    client_id = os.environ.get("VK_CLIENT_ID", DEFAULT_CLIENT_ID).strip() or DEFAULT_CLIENT_ID
    service_token = os.environ.get("VK_SERVICE_TOKEN", "").strip() or None
    state = os.environ.get("VK_OAUTH_STATE", "").strip() or None

    if not refresh_token:
        raise ValueError("VK_REFRESH_TOKEN is not set")
    if not device_id:
        raise ValueError("VK_DEVICE_ID is not set (required for VK ID refresh)")

    tokens = refresh_access_token(
        refresh_token=refresh_token,
        device_id=device_id,
        client_id=client_id,
        service_token=service_token,
        state=state,
    )
    tokens["from_cache"] = False
    save_token_cache(tokens, cache_path)
    os.environ["VK_ACCESS_TOKEN"] = str(tokens["access_token"]).strip()
    meta_path = cache_path.parent / ".vk-oauth-runtime.json"
    try:
        write_runtime_hint(tokens, str(meta_path))
    except OSError:
        pass
    if tokens.get("refresh_token"):
        print(ROTATED_REFRESH_HINT)
    return tokens


def write_runtime_hint(tokens: dict[str, Any], path: str) -> None:
    """Write non-secret metadata only. Never persist tokens to the repo."""
    payload = public_token_meta(tokens)
    payload["note"] = (
        "If VK rotated refresh_token, copy VK_REFRESH_TOKEN from "
        "gitignored memory/site.env.local into Cursor Secret VK_REFRESH_TOKEN "
        "before the next Cloud Agent VM. Do not commit tokens."
    )
    payload["cache_path"] = "memory/site.env.local"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
