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
from typing import Any
from urllib.parse import urlencode

import requests

VK_ID_AUTHORIZE = "https://id.vk.ru/authorize"
VK_ID_TOKEN = "https://id.vk.ru/oauth2/auth"
DEFAULT_CLIENT_ID = "54693054"
DEFAULT_REDIRECT_URI = "http://localhost"
DEFAULT_SCOPE = "groups"


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


def refresh_from_env() -> dict[str, Any]:
    refresh_token = os.environ.get("VK_REFRESH_TOKEN", "").strip()
    device_id = os.environ.get("VK_DEVICE_ID", "").strip()
    client_id = os.environ.get("VK_CLIENT_ID", DEFAULT_CLIENT_ID).strip() or DEFAULT_CLIENT_ID
    service_token = os.environ.get("VK_SERVICE_TOKEN", "").strip() or None
    state = os.environ.get("VK_OAUTH_STATE", "").strip() or None

    if not refresh_token:
        raise ValueError("VK_REFRESH_TOKEN is not set")
    if not device_id:
        raise ValueError("VK_DEVICE_ID is not set (required for VK ID refresh)")

    return refresh_access_token(
        refresh_token=refresh_token,
        device_id=device_id,
        client_id=client_id,
        service_token=service_token,
        state=state,
    )


def write_runtime_hint(tokens: dict[str, Any], path: str) -> None:
    """Write non-secret metadata only. Never persist tokens to the repo."""
    payload = public_token_meta(tokens)
    payload["note"] = (
        "If VK rotated refresh_token, update Cursor Secret VK_REFRESH_TOKEN "
        "from the OAuth JSON you received locally — do not commit tokens."
    )
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
