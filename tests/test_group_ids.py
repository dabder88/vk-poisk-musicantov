"""Tests for multi-group ID parsing and pipeline artifacts."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.group_ids import parse_group_ids
from scripts.vk_client import VkClient


ROOT = Path(__file__).resolve().parents[1]


class ParseGroupIdsTests(unittest.TestCase):
    def test_single_vk_group_id(self) -> None:
        ids = parse_group_ids(group_id="12345", group_ids="")
        self.assertEqual(ids, [12345])

    def test_vk_group_ids_csv(self) -> None:
        ids = parse_group_ids(group_id="", group_ids="111, 222;333")
        self.assertEqual(ids, [111, 222, 333])

    def test_merge_unique_preserve_order(self) -> None:
        ids = parse_group_ids(group_id="222", group_ids="111,222,333")
        self.assertEqual(ids, [111, 222, 333])

    def test_strip_minus(self) -> None:
        ids = parse_group_ids(group_id="-123", group_ids="")
        self.assertEqual(ids, [123])

    def test_empty_raises(self) -> None:
        with self.assertRaises(ValueError):
            parse_group_ids(group_id="", group_ids="")

    def test_from_env(self) -> None:
        with patch.dict(os.environ, {"VK_GROUP_IDS": "10,20", "VK_GROUP_ID": "20"}, clear=False):
            self.assertEqual(parse_group_ids(), [10, 20])


class PipelineMultiGroupTests(unittest.TestCase):
    def test_decide_and_dry_approve_two_groups(self) -> None:
        from scripts.decide import main as decide_main
        from scripts.approve import main as approve_main
        from scripts.validate_run import main as validate_main

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            (run_dir / "requests.json").write_text(
                json.dumps(
                    {
                        "group_ids": [11, 22],
                        "groups": [
                            {"group_id": 11, "count": 2, "user_ids": [101, 102]},
                            {"group_id": 22, "count": 1, "user_ids": [201]},
                        ],
                        "count": 3,
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "context.json").write_text(
                json.dumps({"run_id": "t", "group_ids": [11, 22]}),
                encoding="utf-8",
            )

            with patch("sys.argv", ["decide.py", "--run-dir", str(run_dir)]):
                self.assertEqual(decide_main(), 0)
            decision = json.loads((run_dir / "decision.json").read_text(encoding="utf-8"))
            self.assertEqual(decision["summary"]["approve"], 3)
            self.assertEqual(
                decision["to_approve"],
                [
                    {"group_id": 11, "user_id": 101},
                    {"group_id": 11, "user_id": 102},
                    {"group_id": 22, "user_id": 201},
                ],
            )

            env = {"APPROVE_ALLOW": "no", "DRY_RUN": "yes"}
            with patch.dict(os.environ, env, clear=False):
                with patch(
                    "sys.argv",
                    ["approve.py", "--run-dir", str(run_dir), "--run-id", "t"],
                ):
                    self.assertEqual(approve_main(), 0)
            results = json.loads((run_dir / "approve-results.json").read_text(encoding="utf-8"))
            self.assertEqual(results["mode"], "dry_run")
            self.assertEqual(len(results["results"]), 3)
            self.assertEqual({r["group_id"] for r in results["results"]}, {11, 22})

            with patch(
                "sys.argv",
                ["validate.py", "--run-dir", str(run_dir), "-o", str(run_dir / "qa.json")],
            ):
                self.assertEqual(validate_main(), 0)
            qa = json.loads((run_dir / "qa.json").read_text(encoding="utf-8"))
            self.assertEqual(qa["status"], "PASS")

    def test_client_with_group_shares_token(self) -> None:
        a = VkClient("tok", 1)
        b = a.with_group(2)
        self.assertEqual(b.group_id, 2)
        self.assertEqual(b.access_token, "tok")
        self.assertEqual(a.group_id, 1)


if __name__ == "__main__":
    unittest.main()
