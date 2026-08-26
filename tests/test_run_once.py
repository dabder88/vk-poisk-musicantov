from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from scripts.run_once import load_local_env


class LoadLocalEnvTests(unittest.TestCase):
    def test_loads_missing_keys_only(self) -> None:
        os.environ.pop("VK_GROUP_ID", None)
        os.environ["VK_DEVICE_ID"] = "already"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "local.env"
            path.write_text(
                "VK_GROUP_ID=1,2,3\nVK_DEVICE_ID=fromfile\n# comment\n\n",
                encoding="utf-8",
            )
            load_local_env(path)
        self.assertEqual(os.environ.get("VK_GROUP_ID"), "1,2,3")
        self.assertEqual(os.environ.get("VK_DEVICE_ID"), "already")
        os.environ.pop("VK_GROUP_ID", None)
        os.environ.pop("VK_DEVICE_ID", None)

    def test_reads_utf16_and_txt_suffix(self) -> None:
        os.environ.pop("VK_GROUP_ID", None)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "local.env.txt"
            path.write_text("VK_GROUP_ID=9,8,7\n", encoding="utf-16")
            load_local_env(Path(tmp) / "local.env")
        self.assertEqual(os.environ.get("VK_GROUP_ID"), "9,8,7")
        os.environ.pop("VK_GROUP_ID", None)


if __name__ == "__main__":
    unittest.main()
