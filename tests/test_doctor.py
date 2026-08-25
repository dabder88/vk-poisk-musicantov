"""Doctor preflight: catch access_token stuffed into VK_REFRESH_TOKEN without HTTP."""

from __future__ import annotations

import io
import os
import unittest
from unittest.mock import patch

from scripts.doctor import (
    HINT_REFRESH_TOKEN_IS_ACCESS,
    looks_like_vk_access_token,
    main as doctor_main,
)


class RefreshPrefixTests(unittest.TestCase):
    def test_vk2_a_is_access_token(self) -> None:
        self.assertTrue(looks_like_vk_access_token("  vk2.a.not-a-secret-fixture  "))
        self.assertFalse(looks_like_vk_access_token("vk2.r.not-a-secret-fixture"))
        self.assertFalse(looks_like_vk_access_token(""))

    def test_doctor_fails_access_prefix_without_http(self) -> None:
        env = {
            "VK_GROUP_ID": "12345",
            "VK_GROUP_IDS": "",
            "VK_ACCESS_TOKEN": "vk2.a.fixture-access",
            "VK_REFRESH_TOKEN": "vk2.a.fixture-refresh-slot",
            "VK_DEVICE_ID": "device-fixture",
            "VK_SERVICE_TOKEN": "svc-fixture",
            "APPROVE_ALLOW": "no",
            "DRY_RUN": "yes",
        }
        buf = io.StringIO()
        with patch.dict(os.environ, env, clear=False):
            with patch("scripts.doctor.VkClient.from_env") as from_env:
                with patch("sys.stdout", buf):
                    code = doctor_main()
        self.assertEqual(code, 1)
        from_env.assert_not_called()
        out = buf.getvalue()
        self.assertIn("ERROR VK_REFRESH_TOKEN starts with vk2.a.", out)
        self.assertIn(HINT_REFRESH_TOKEN_IS_ACCESS, out)
        self.assertIn("vk2.r.", out)
        self.assertIn("get_vk_token.py start", out)
        self.assertIn("finish --redirect-url", out)
        self.assertNotIn("fixture-refresh-slot", out)
        self.assertNotIn("fixture-access", out)
        self.assertNotIn("svc-fixture", out)


if __name__ == "__main__":
    unittest.main()
