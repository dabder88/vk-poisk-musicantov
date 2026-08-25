"""Shared VK API client for join-request automation."""

from __future__ import annotations

import os
from typing import Any

import requests

DEFAULT_API_VERSION = "5.199"
API_BASE = "https://api.vk.com/method"


class VkApiError(Exception):
    def __init__(self, code: int, message: str, method: str) -> None:
        self.code = code
        self.message = message
        self.method = method
        super().__init__(f"VK API {method} error {code}: {message}")


class VkClient:
    def __init__(
        self,
        access_token: str,
        group_id: int,
        api_version: str = DEFAULT_API_VERSION,
    ) -> None:
        self.access_token = access_token
        self.group_id = group_id
        self.api_version = api_version

    def with_group(self, group_id: int) -> "VkClient":
        """Same token, another group (no extra OAuth refresh)."""
        return VkClient(
            access_token=self.access_token,
            group_id=int(group_id),
            api_version=self.api_version,
        )

    @classmethod
    def from_env(cls, *, refresh: bool = True, group_id: int | None = None) -> "VkClient":
        from scripts.group_ids import parse_group_ids

        token = os.environ.get("VK_ACCESS_TOKEN", "").strip()
        version = os.environ.get("VK_API_VERSION", DEFAULT_API_VERSION).strip()
        ids = parse_group_ids()
        resolved = int(group_id) if group_id is not None else ids[0]

        if refresh and os.environ.get("VK_REFRESH_TOKEN", "").strip():
            from scripts.vk_oauth import public_token_meta, refresh_from_env

            tokens = refresh_from_env()
            token = str(tokens["access_token"]).strip()
            meta = public_token_meta(tokens)
            print(
                "OK VK ID refresh_token exchanged on this host "
                f"user_id={meta.get('user_id')} scope={meta.get('scope')}"
            )
            if tokens.get("refresh_token"):
                print(
                    "WARN if VK rotated refresh_token, update Cursor Secret "
                    "VK_REFRESH_TOKEN before the next run"
                )

        if not token:
            raise ValueError(
                "VK_ACCESS_TOKEN is not set "
                "(set VK_REFRESH_TOKEN+VK_DEVICE_ID to refresh on this host)"
            )

        return cls(
            access_token=token,
            group_id=resolved,
            api_version=version,
        )

    def call(self, method: str, **params: Any) -> Any:
        payload = {
            "access_token": self.access_token,
            "v": self.api_version,
            **params,
        }
        response = requests.post(
            f"{API_BASE}/{method}",
            data=payload,
            timeout=30,
        )
        response.raise_for_status()
        body = response.json()

        if "error" in body:
            err = body["error"]
            raise VkApiError(
                code=int(err.get("error_code", -1)),
                message=str(err.get("error_msg", "unknown")),
                method=method,
            )

        return body.get("response")

    def get_requests(self, count: int = 100, offset: int = 0) -> list[int]:
        response = self.call(
            "groups.getRequests",
            group_id=self.group_id,
            count=count,
            offset=offset,
        )
        if not response:
            return []
        if isinstance(response, dict):
            items = response.get("items", [])
            return [int(x) for x in items]
        return [int(x) for x in response]

    def approve_request(self, user_id: int) -> bool:
        result = self.call(
            "groups.approveRequest",
            group_id=self.group_id,
            user_id=user_id,
        )
        return int(result) == 1

    def probe_token(self) -> dict[str, Any]:
        """Smoke-test: can we list join requests?"""
        try:
            requests_list = self.get_requests(count=1)
            return {
                "ok": True,
                "method": "groups.getRequests",
                "pending_count_sample": len(requests_list),
            }
        except VkApiError as exc:
            return {
                "ok": False,
                "method": "groups.getRequests",
                "error_code": exc.code,
                "error_message": exc.message,
            }
