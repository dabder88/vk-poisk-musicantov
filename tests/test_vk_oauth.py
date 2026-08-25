"""Unit tests for VK ID refresh (mocked HTTP)."""

from __future__ import annotations

import io
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.vk_oauth import (
    authorize_url,
    load_token_cache,
    public_token_meta,
    refresh_access_token,
    refresh_from_env,
    write_runtime_hint,
)
from scripts.vk_client import VkApiError, VkClient


TOKEN_PAYLOAD = {
    "access_token": "vk2.a.cached-access",
    "refresh_token": "vk2.r.rotated-refresh",
    "user_id": 4253689,
    "scope": "vkid.personal_info groups",
    "expires_in": 3600,
    "token_type": "Bearer",
}


class AuthorizeUrlTests(unittest.TestCase):
    def test_authorize_url_is_vk_id_code_flow(self) -> None:
        url = authorize_url(
            code_challenge="abc",
            state="state-value-must-be-long-enough-0123456789",
        )
        self.assertTrue(url.startswith("https://id.vk.ru/authorize?"))
        self.assertIn("response_type=code", url)
        self.assertIn("scope=groups", url)
        self.assertIn("code_challenge_method=S256", url)
        self.assertIn("prompt=consent", url)
        self.assertNotIn("oauth.vk.com", url)
        self.assertNotIn("response_type=token", url)


class RefreshTests(unittest.TestCase):
    def test_refresh_posts_grant_type_refresh_token(self) -> None:
        payload = {
            "access_token": "vk2.a.new",
            "refresh_token": "vk2.r.new",
            "user_id": 4253689,
            "scope": "vkid.personal_info groups",
            "expires_in": 3600,
            "token_type": "Bearer",
        }
        with patch("scripts.vk_oauth.requests.post") as post:
            post.return_value.status_code = 200
            post.return_value.json.return_value = payload
            post.return_value.raise_for_status.return_value = None
            out = refresh_access_token(
                refresh_token="old-refresh",
                device_id="device-1",
                client_id="54693054",
                service_token="svc",
            )
        self.assertEqual(out["access_token"], "vk2.a.new")
        sent = post.call_args.kwargs["data"]
        self.assertEqual(sent["grant_type"], "refresh_token")
        self.assertEqual(sent["refresh_token"], "old-refresh")
        self.assertEqual(sent["device_id"], "device-1")
        self.assertEqual(sent["service_token"], "svc")
        self.assertEqual(sent["scope"], "groups")
        self.assertEqual(post.call_args.args[0], "https://id.vk.ru/oauth2/auth")

    def test_public_meta_strips_secrets(self) -> None:
        meta = public_token_meta(
            {
                "access_token": "secret-access",
                "refresh_token": "secret-refresh",
                "user_id": 1,
                "scope": "groups",
            }
        )
        dumped = str(meta)
        self.assertNotIn("secret-access", dumped)
        self.assertNotIn("secret-refresh", dumped)
        self.assertTrue(meta["refresh_token_present"])
        self.assertEqual(meta["access_token_len"], len("secret-access"))

    def test_runtime_hint_file_has_no_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hint.json"
            write_runtime_hint(
                {
                    "access_token": "secret-access",
                    "refresh_token": "secret-refresh",
                    "user_id": 9,
                    "scope": "groups",
                },
                str(path),
            )
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("secret-access", text)
            self.assertNotIn("secret-refresh", text)
            payload = json.loads(text)
            self.assertEqual(payload["user_id"], 9)
            self.assertEqual(payload["cache_path"], "memory/site.env.local")

    def test_refresh_from_env_requires_device_id(self) -> None:
        env = {"VK_REFRESH_TOKEN": "r", "VK_TOKEN_CACHE_PATH": "/tmp/missing-vk-cache.env"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ValueError) as ctx:
                refresh_from_env()
        self.assertIn("VK_DEVICE_ID", str(ctx.exception))


class TokenCacheTests(unittest.TestCase):
    def test_refresh_writes_cache_then_reuses_without_second_http(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "site.env.local"
            env = {
                "VK_REFRESH_TOKEN": "dashboard-refresh",
                "VK_DEVICE_ID": "dev",
                "VK_CLIENT_ID": "54693054",
                "VK_TOKEN_CACHE_PATH": str(cache),
                "VK_GROUP_ID": "111",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("scripts.vk_oauth.requests.post") as post:
                    post.return_value.status_code = 200
                    post.return_value.json.return_value = dict(TOKEN_PAYLOAD)
                    post.return_value.raise_for_status.return_value = None
                    stdout = io.StringIO()
                    with patch("sys.stdout", stdout):
                        first = refresh_from_env()
                        second = refresh_from_env()
                        client = VkClient.from_env()
                    logged = stdout.getvalue()
            self.assertEqual(post.call_count, 1)
            self.assertEqual(first["access_token"], TOKEN_PAYLOAD["access_token"])
            self.assertFalse(first.get("from_cache"))
            self.assertTrue(second.get("from_cache"))
            self.assertEqual(second["access_token"], TOKEN_PAYLOAD["access_token"])
            self.assertEqual(client.access_token, TOKEN_PAYLOAD["access_token"])
            self.assertTrue(cache.is_file())
            self.assertEqual(stat.S_IMODE(cache.stat().st_mode), 0o600)
            cached = load_token_cache(cache)
            self.assertEqual(cached["VK_ACCESS_TOKEN"], TOKEN_PAYLOAD["access_token"])
            self.assertEqual(cached["VK_REFRESH_TOKEN"], TOKEN_PAYLOAD["refresh_token"])
            self.assertEqual(cached["VK_TOKEN_USER_ID"], "4253689")
            self.assertNotIn(TOKEN_PAYLOAD["access_token"], logged)
            self.assertNotIn(TOKEN_PAYLOAD["refresh_token"], logged)
            self.assertNotIn("dashboard-refresh", logged)
            self.assertIn("memory/site.env.local", logged)
            meta_path = cache.parent / ".vk-oauth-runtime.json"
            meta_text = meta_path.read_text(encoding="utf-8")
            self.assertNotIn(TOKEN_PAYLOAD["access_token"], meta_text)
            self.assertNotIn(TOKEN_PAYLOAD["refresh_token"], meta_text)

    def test_force_refresh_is_the_only_second_http_exchange(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "site.env.local"
            env = {
                "VK_REFRESH_TOKEN": "dashboard-refresh",
                "VK_DEVICE_ID": "dev",
                "VK_TOKEN_CACHE_PATH": str(cache),
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("scripts.vk_oauth.requests.post") as post:
                    post.return_value.status_code = 200
                    post.return_value.json.return_value = dict(TOKEN_PAYLOAD)
                    post.return_value.raise_for_status.return_value = None
                    refresh_from_env()
                    refresh_from_env()
                    refresh_from_env(force=True)
            self.assertEqual(post.call_count, 2)
            sent = post.call_args.kwargs["data"]
            self.assertEqual(sent["refresh_token"], TOKEN_PAYLOAD["refresh_token"])


class VkClientFromEnvTests(unittest.TestCase):
    def test_from_env_refreshes_before_api(self) -> None:
        tokens = {
            "access_token": "refreshed-token",
            "refresh_token": "rotated",
            "user_id": 4253689,
            "scope": "groups",
            "from_cache": False,
        }
        env = {
            "VK_GROUP_ID": "12345",
            "VK_GROUP_IDS": "",
            "VK_ACCESS_TOKEN": "stale-ip-token",
            "VK_REFRESH_TOKEN": "refresh",
            "VK_DEVICE_ID": "dev",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("scripts.vk_oauth.refresh_from_env", return_value=tokens):
                with patch("scripts.vk_oauth.load_token_cache", return_value={}):
                    client = VkClient.from_env()
        self.assertEqual(client.access_token, "refreshed-token")
        self.assertEqual(client.group_id, 12345)

    def test_probe_maps_error_5(self) -> None:
        client = VkClient(access_token="x", group_id=1)
        with patch.object(
            client,
            "get_requests",
            side_effect=VkApiError(
                5,
                "access_token was given to another ip address",
                "groups.getRequests",
            ),
        ):
            probe = client.probe_token()
        self.assertFalse(probe["ok"])
        self.assertEqual(probe["error_code"], 5)

    def test_get_requests_retries_error_5_same_token(self) -> None:
        client = VkClient(access_token="host-bound", group_id=1)
        err = VkApiError(
            5,
            "access_token was given to another ip address",
            "groups.getRequests",
        )
        with patch.object(client, "call", side_effect=[err, err, {"items": [7]}]) as call:
            with patch("scripts.vk_client.time.sleep", return_value=None):
                items = client.get_requests(count=1)
        self.assertEqual(items, [7])
        self.assertEqual(call.call_count, 3)


if __name__ == "__main__":
    unittest.main()
