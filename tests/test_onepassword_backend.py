from __future__ import annotations

import subprocess
import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from scripts_py.lib.password_manager import OnePasswordBackend


class TestOnePasswordBackend(unittest.TestCase):
    def test_check_logged_in_missing_binary(self) -> None:
        with patch("shutil.which", return_value=None):
            res = OnePasswordBackend().check_logged_in()
        self.assertFalse(res.ok)
        self.assertIsNotNone(res.hint)
        assert res.hint is not None
        self.assertIn("op", res.hint)

    def test_check_logged_in_not_signed_in(self) -> None:
        with patch("shutil.which", return_value="/bin/op"):
            with patch(
                "subprocess.run",
                return_value=SimpleNamespace(
                    returncode=1, stdout="", stderr="account is not signed in"
                ),
            ):
                res = OnePasswordBackend().check_logged_in()
        self.assertFalse(res.ok)
        self.assertEqual(res.hint, "account is not signed in")

    def test_check_logged_in_success(self) -> None:
        with patch("shutil.which", return_value="/bin/op"):
            with patch(
                "subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout="", stderr=""),
            ):
                res = OnePasswordBackend().check_logged_in()
        self.assertTrue(res.ok)

    def test_format_help_message_contains_op_signin(self) -> None:
        msg = OnePasswordBackend().format_help_message(hint=None)
        self.assertIn("op signin", msg)
        self.assertIn("1Password", msg)

    def test_format_help_message_includes_details(self) -> None:
        msg = OnePasswordBackend().format_help_message(hint="account is not signed in")
        self.assertIn("account is not signed in", msg)

    def test_store_secret_missing_binary(self) -> None:
        with patch("shutil.which", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                OnePasswordBackend().store_secret(
                    entry_path="test/secret", value="val", username=None
                )
        self.assertIn("op", str(ctx.exception))

    def test_try_signin_missing_binary(self) -> None:
        with patch("shutil.which", return_value=None):
            res = OnePasswordBackend().try_signin()
        self.assertFalse(res.ok)

    def test_try_signin_success(self) -> None:
        calls: list[tuple[Any, dict[str, Any]]] = []

        def fake_run(cmd: Any, **kwargs: Any) -> SimpleNamespace:
            calls.append((cmd, kwargs))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch("shutil.which", return_value="/bin/op"):
            with patch("subprocess.run", side_effect=fake_run):
                res = OnePasswordBackend().try_signin()
        self.assertTrue(res.ok)
        # Should have called op signin then op whoami
        self.assertEqual(calls[0][0], ["/bin/op", "signin"])
        self.assertEqual(calls[1][0], ["/bin/op", "whoami"])

    def test_try_signin_fails(self) -> None:
        with patch("shutil.which", return_value="/bin/op"):
            with patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(1, "op signin"),
            ):
                res = OnePasswordBackend().try_signin()
        self.assertFalse(res.ok)

    def test_store_secret_not_signed_in(self) -> None:
        with patch("shutil.which", return_value="/bin/op"):
            with patch(
                "subprocess.run",
                return_value=SimpleNamespace(returncode=1, stdout="", stderr="not signed in"),
            ):
                with self.assertRaises(RuntimeError) as ctx:
                    OnePasswordBackend().store_secret(
                        entry_path="test/secret", value="val", username=None
                    )
        self.assertIn("op signin", str(ctx.exception))

    def test_store_secret_invokes_op_item_create(self) -> None:
        calls: list[tuple[Any, dict[str, Any]]] = []

        def fake_run(cmd: Any, **kwargs: Any) -> SimpleNamespace:
            calls.append((cmd, kwargs))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch("shutil.which", return_value="/bin/op"):
            with patch("subprocess.run", side_effect=fake_run):
                OnePasswordBackend().store_secret(
                    entry_path="secretspec/myproj/default/API_KEY",
                    value="secret123",
                    username="svc-user",
                )

        # first call: op whoami
        self.assertEqual(calls[0][0], ["/bin/op", "whoami"])

        # second call: op item create -
        create_cmd, create_kwargs = calls[1]
        self.assertEqual(create_cmd, ["/bin/op", "item", "create", "-"])
        self.assertIn("input", create_kwargs)
        self.assertIn("secretspec/myproj/default/API_KEY", create_kwargs["input"])
        self.assertIn("secret123", create_kwargs["input"])
        self.assertIn("svc-user", create_kwargs["input"])
        self.assertTrue(create_kwargs["check"])

    def test_store_secret_without_username(self) -> None:
        calls: list[tuple[Any, dict[str, Any]]] = []

        def fake_run(cmd: Any, **kwargs: Any) -> SimpleNamespace:
            calls.append((cmd, kwargs))
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch("shutil.which", return_value="/bin/op"):
            with patch("subprocess.run", side_effect=fake_run):
                OnePasswordBackend().store_secret(
                    entry_path="secretspec/myproj/default/TOKEN",
                    value="tok",
                    username=None,
                )

        create_kwargs = calls[1][1]
        self.assertNotIn("username", create_kwargs["input"])


if __name__ == "__main__":
    unittest.main()
