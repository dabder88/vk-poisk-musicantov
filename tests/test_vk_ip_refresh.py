"""Tests: one extra refresh after IP retries; fetch writes partial requests.json."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.fetch_requests import main as fetch_main
from scripts.vk_client import VkApiError, VkClient
from scripts.vk_ip_refresh import (
    OneExtraRefresh,
    ip_probe_failed,
    run_per_group_with_one_extra_refresh,
)


IP_ERR = VkApiError(5, "access_token was given to another ip address", "groups.getRequests")


def _ip_call(self: VkClient, method: str, **params):
    gid = int(params["group_id"])
    if self.access_token == "cached":
        if gid == 11:
            return {"items": [101, 102]}
        raise IP_ERR
    return {"items": [gid]}


class OneExtraRefreshTests(unittest.TestCase):
    def test_cache_success_does_not_force_refresh(self) -> None:
        client = VkClient(access_token="cached", group_id=11)
        refresh_calls: list[bool] = []

        def fake_refresh(*, force: bool = False):
            refresh_calls.append(force)
            return {"access_token": "new"}

        def fetch_one(bound: VkClient, gid: int) -> list[int]:
            return bound.with_group(gid).get_requests(count=1)

        with patch("scripts.vk_oauth.refresh_from_env", side_effect=fake_refresh):
            with patch.object(VkClient, "call", _ip_call):
                with patch("scripts.vk_client.time.sleep", return_value=None):
                    _client, latest = run_per_group_with_one_extra_refresh(
                        client, [11], fetch_one
                    )
        self.assertEqual(latest[11], [101, 102])
        self.assertEqual(refresh_calls, [])

    def test_extra_refresh_only_after_ip_retries(self) -> None:
        client = VkClient(access_token="cached", group_id=11)
        call_tokens: list[str] = []
        refresh_calls: list[bool] = []

        def tracking_call(self: VkClient, method: str, **params):
            call_tokens.append(self.access_token)
            return _ip_call(self, method, **params)

        def fake_refresh(*, force: bool = False):
            refresh_calls.append(force)
            return {"access_token": "rotated-host"}

        def fetch_one(bound: VkClient, gid: int) -> dict:
            ids = bound.with_group(gid).get_requests(count=10)
            return {"group_id": gid, "user_ids": ids}

        with patch("scripts.vk_oauth.refresh_from_env", side_effect=fake_refresh):
            with patch.object(VkClient, "call", tracking_call):
                with patch("scripts.vk_client.time.sleep", return_value=None):
                    _client, latest = run_per_group_with_one_extra_refresh(
                        client, [11, 22, 33], fetch_one
                    )

        self.assertEqual(refresh_calls, [True])
        self.assertEqual(client.access_token, "rotated-host")
        self.assertEqual(latest[11]["user_ids"], [101, 102])
        self.assertEqual(latest[22]["user_ids"], [22])
        self.assertEqual(latest[33]["user_ids"], [33])
        self.assertGreaterEqual(call_tokens.count("cached"), 1 + 3 + 3)
        self.assertIn("rotated-host", call_tokens)

    def test_no_second_extra_refresh_if_still_ip(self) -> None:
        client = VkClient(access_token="cached", group_id=11)
        refresh_calls: list[bool] = []

        def always_ip(self: VkClient, method: str, **params):
            raise IP_ERR

        def fake_refresh(*, force: bool = False):
            refresh_calls.append(force)
            return {"access_token": "rotated-host"}

        def fetch_one(bound: VkClient, gid: int) -> list[int]:
            return bound.with_group(gid).get_requests(count=1)

        with patch("scripts.vk_oauth.refresh_from_env", side_effect=fake_refresh):
            with patch.object(VkClient, "call", always_ip):
                with patch("scripts.vk_client.time.sleep", return_value=None):
                    _client, latest = run_per_group_with_one_extra_refresh(
                        client, [11, 22], fetch_one
                    )
        self.assertEqual(refresh_calls, [True])
        self.assertIsInstance(latest[11], VkApiError)
        self.assertEqual(latest[11].code, 5)

    def test_maybe_apply_second_call_is_noop(self) -> None:
        extra = OneExtraRefresh()
        client = VkClient(access_token="a", group_id=1)
        with patch(
            "scripts.vk_oauth.refresh_from_env",
            return_value={"access_token": "b"},
        ) as refresh:
            self.assertTrue(extra.maybe_apply(client))
            self.assertFalse(extra.maybe_apply(client))
        self.assertEqual(refresh.call_count, 1)
        refresh.assert_called_once_with(force=True)

    def test_probe_ip_from_result_triggers_one_refresh(self) -> None:
        client = VkClient(access_token="cached", group_id=11)
        refresh_calls: list[bool] = []

        def fake_refresh(*, force: bool = False):
            refresh_calls.append(force)
            return {"access_token": "rotated-host"}

        def probe_one(bound: VkClient, gid: int) -> dict:
            return bound.with_group(gid).probe_token()

        with patch("scripts.vk_oauth.refresh_from_env", side_effect=fake_refresh):
            with patch.object(VkClient, "call", _ip_call):
                with patch("scripts.vk_client.time.sleep", return_value=None):
                    _client, latest = run_per_group_with_one_extra_refresh(
                        client,
                        [11, 22],
                        probe_one,
                        ip_from_result=ip_probe_failed,
                    )
        self.assertEqual(refresh_calls, [True])
        self.assertTrue(latest[11]["ok"])
        self.assertTrue(latest[22]["ok"])


class FetchWritesPartialTests(unittest.TestCase):
    def test_fetch_writes_json_and_one_force_refresh(self) -> None:
        client = VkClient(access_token="cached", group_id=11)
        refresh_calls: list[bool] = []

        def fake_refresh(*, force: bool = False):
            refresh_calls.append(force)
            return {"access_token": "rotated-host"}

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            env = {
                "VK_GROUP_IDS": "11,22,33",
                "VK_GROUP_ID": "",
                "VK_ACCESS_TOKEN": "cached",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("scripts.fetch_requests.VkClient.from_env", return_value=client):
                    with patch("scripts.vk_oauth.refresh_from_env", side_effect=fake_refresh):
                        with patch.object(VkClient, "call", _ip_call):
                            with patch("scripts.vk_client.time.sleep", return_value=None):
                                with patch("sys.stdout", io.StringIO()):
                                    with patch(
                                        "sys.argv",
                                        ["fetch_requests.py", "--run-dir", str(run_dir)],
                                    ):
                                        rc = fetch_main()
            payload = json.loads((run_dir / "requests.json").read_text(encoding="utf-8"))
        self.assertEqual(rc, 0)
        self.assertEqual(refresh_calls, [True])
        self.assertEqual(payload["count"], 4)
        self.assertFalse(payload["partial"])
        self.assertEqual(payload["groups"][0]["user_ids"], [101, 102])
        self.assertEqual(payload["groups"][1]["user_ids"], [22])
        self.assertEqual(payload["groups"][2]["user_ids"], [33])

    def test_fetch_writes_partial_when_ip_sticky_after_one_refresh(self) -> None:
        client = VkClient(access_token="cached", group_id=11)

        def always_ip(self: VkClient, method: str, **params):
            raise IP_ERR

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            env = {
                "VK_GROUP_IDS": "11,22",
                "VK_GROUP_ID": "",
                "VK_ACCESS_TOKEN": "cached",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("scripts.fetch_requests.VkClient.from_env", return_value=client):
                    with patch(
                        "scripts.vk_oauth.refresh_from_env",
                        return_value={"access_token": "rotated-host"},
                    ) as refresh:
                        with patch.object(VkClient, "call", always_ip):
                            with patch("scripts.vk_client.time.sleep", return_value=None):
                                with patch("sys.stdout", io.StringIO()):
                                    with patch(
                                        "sys.argv",
                                        ["fetch_requests.py", "--run-dir", str(run_dir)],
                                    ):
                                        rc = fetch_main()
            payload = json.loads((run_dir / "requests.json").read_text(encoding="utf-8"))
            self.assertTrue((run_dir / "requests.json").is_file())
        self.assertEqual(rc, 1)
        self.assertEqual(refresh.call_count, 1)
        refresh.assert_called_with(force=True)
        self.assertTrue(payload["partial"])
        self.assertEqual(payload["errors"], 2)
        self.assertEqual(payload["groups"][0]["error_code"], 5)
        self.assertEqual(payload["groups"][1]["count"], 0)

    def test_fetch_success_from_cache_no_force_refresh(self) -> None:
        client = VkClient(access_token="cached", group_id=11)

        def always_ok(self: VkClient, method: str, **params):
            return {"items": [int(params["group_id"])]}

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            env = {
                "VK_GROUP_IDS": "11,22",
                "VK_GROUP_ID": "",
                "VK_ACCESS_TOKEN": "cached",
            }
            with patch.dict(os.environ, env, clear=False):
                with patch("scripts.fetch_requests.VkClient.from_env", return_value=client):
                    with patch("scripts.vk_oauth.refresh_from_env") as refresh:
                        with patch.object(VkClient, "call", always_ok):
                            with patch("sys.stdout", io.StringIO()):
                                with patch(
                                    "sys.argv",
                                    ["fetch_requests.py", "--run-dir", str(run_dir)],
                                ):
                                    rc = fetch_main()
            payload = json.loads((run_dir / "requests.json").read_text(encoding="utf-8"))
        self.assertEqual(rc, 0)
        refresh.assert_not_called()
        self.assertEqual(payload["count"], 2)
        self.assertFalse(payload["partial"])


if __name__ == "__main__":
    unittest.main()
