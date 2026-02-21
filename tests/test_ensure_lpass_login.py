from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts_py.ensure_lpass_login import check_lpass_logged_in


class TestEnsureLpassLogin(unittest.TestCase):
    def test_check_lpass_logged_in_missing_binary(self) -> None:
        with patch("shutil.which", return_value=None):
            res = check_lpass_logged_in()
        self.assertFalse(res.ok)
        self.assertIsNotNone(res.hint)
        assert res.hint is not None
        self.assertIn("lpass", res.hint)

    def test_check_lpass_logged_in_not_logged_in(self) -> None:
        with patch("shutil.which", return_value="/bin/lpass"):
            with patch(
                "subprocess.run",
                return_value=SimpleNamespace(returncode=1, stdout="", stderr="Not logged in"),
            ):
                res = check_lpass_logged_in()

        self.assertFalse(res.ok)
        self.assertEqual(res.hint, "Not logged in")


if __name__ == "__main__":
    unittest.main()
