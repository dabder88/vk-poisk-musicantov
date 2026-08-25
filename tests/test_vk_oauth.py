"""Unit tests for VK ID refresh (mocked HTTP)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from scripts.vk_oauth import (
    authorize_url,
    public_token_meta,
    refresh_access_token,
    refresh_from_env,
)
from scripts.vk_client import VkClient, VkApiError


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

    def test_refresh_from_env_requires_device_id(self) -> None:
        env = {"VK_REFRESH_TOKEN": "r"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ValueError) as ctx:
                refresh_from_env()
        self.assertIn("VK_DEVICE_ID", str(ctx.exception))


class VkClientFromEnvTests(unittest.TestCase):
    def test_from_env_refreshes_before_api(self) -> None:
        tokens = {
            "access_token": "refreshed-token",
            "refresh_token": "rotated",
            "user_id": 4253689,
            "scope": "groups",
        }
        env = {
            "VK_GROUP_ID": "12345",
            "VK_ACCESS_TOKEN": "stale-ip-token",
            "VK_REFRESH_TOKEN": "refresh",
            "VK_DEVICE_ID": "dev",
        }
        with patch.dict(os.environ, env, clear=False):
            with patch("scripts.vk_oauth.refresh_from_env", return_value=tokens):
                client = VkClient.from_env()
        self.assertEqual(client.access_token, "refreshed-token")
        self.assertEqual(client.group_id, 12345)

    def test_probe_maps_error_5(self) -> None:
        client = VkClient(access_token="x", group_id=1)
        with patch.object(
            client,
            "get_requests",
            side_effect=VkApiError(5, "access_token was given to another ip address", "groups.getRequests"),
        ):
            probe = client.probe_token()
        self.assertFalse(probe["ok"])
        self.assertEqual(probe["error_code"], 5)


if __name__ == "__main__":
    unittest.main()
