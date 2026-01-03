from __future__ import annotations

import unittest

from scripts_py.sync_github_labels import LabelSpec, normalize_color, plan_changes


class TestNormalizeColor(unittest.TestCase):
    def test_accepts_hash_prefixed(self) -> None:
        self.assertEqual(normalize_color("#AaBbCc"), "aabbcc")

    def test_rejects_non_hex(self) -> None:
        with self.assertRaises(ValueError):
            normalize_color("zzzzzz")


class TestPlanChanges(unittest.TestCase):
    def test_create_and_update_and_delete(self) -> None:
        desired = [
            LabelSpec(name="dependencies", color="0366d6", description="deps"),
            LabelSpec(name="github-actions", color="000000", description="gha"),
        ]
        existing = {
            "dependencies": {"name": "dependencies", "color": "ffffff", "description": "deps"},
            "old": {"name": "old", "color": "ff00ff", "description": ""},
        }

        to_create, to_update, to_delete = plan_changes(desired, existing, delete_unmanaged=True)

        self.assertEqual([s.name for s in to_create], ["github-actions"])
        self.assertEqual([s.name for s in to_update], ["dependencies"])
        self.assertEqual(to_delete, ["old"])


if __name__ == "__main__":
    unittest.main()
