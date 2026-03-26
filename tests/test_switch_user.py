from __future__ import annotations

import unittest
from collections.abc import Sequence

from scripts_py.cli.switch_user import build_gdbus_argv, build_lock_argv, main, switch_to_user


class CapturingRunner:
    """Test double that records calls and returns pre-configured return codes."""

    def __init__(self, return_codes: list[int]) -> None:
        self._codes = iter(return_codes)
        self.calls: list[list[str]] = []

    def run(self, argv: Sequence[str]) -> int:
        self.calls.append(list(argv))
        return next(self._codes)


class TestBuildGdbusArgv(unittest.TestCase):
    def test_targets_system_bus(self) -> None:
        argv = build_gdbus_argv("ilmari")
        self.assertIn("--system", argv)

    def test_targets_gdm_manager_object(self) -> None:
        argv = build_gdbus_argv("ilmari")
        self.assertIn("/org/gnome/DisplayManager/Manager", argv)

    def test_calls_switch_to_user_method(self) -> None:
        argv = build_gdbus_argv("ilmari")
        self.assertIn("org.gnome.DisplayManager.Manager.SwitchToUser", argv)

    def test_includes_target_user(self) -> None:
        argv = build_gdbus_argv("ilmari")
        self.assertIn("ilmari", argv)

    def test_different_target_user(self) -> None:
        argv = build_gdbus_argv("tapiiri")
        self.assertIn("tapiiri", argv)
        self.assertNotIn("ilmari", argv)


class TestBuildLockArgv(unittest.TestCase):
    def test_calls_loginctl(self) -> None:
        argv = build_lock_argv()
        self.assertEqual(argv[0], "loginctl")

    def test_lock_session_subcommand(self) -> None:
        argv = build_lock_argv()
        self.assertIn("lock-session", argv)


class TestSwitchToUser(unittest.TestCase):
    def test_gdbus_success_returns_zero(self) -> None:
        runner = CapturingRunner([0])
        rc = switch_to_user("ilmari", runner)
        self.assertEqual(rc, 0)
        self.assertEqual(len(runner.calls), 1)

    def test_gdbus_success_does_not_call_fallback(self) -> None:
        runner = CapturingRunner([0])
        switch_to_user("ilmari", runner)
        # Only one call — no loginctl fallback
        self.assertNotIn("loginctl", runner.calls[0])

    def test_gdbus_failure_falls_back_to_lock(self) -> None:
        runner = CapturingRunner([1, 0])
        rc = switch_to_user("ilmari", runner)
        self.assertEqual(rc, 0)
        self.assertEqual(len(runner.calls), 2)
        self.assertIn("loginctl", runner.calls[1])

    def test_gdbus_failure_lock_success_returns_zero(self) -> None:
        runner = CapturingRunner([1, 0])
        rc = switch_to_user("ilmari", runner)
        self.assertEqual(rc, 0)

    def test_both_fail_returns_nonzero(self) -> None:
        runner = CapturingRunner([1, 1])
        rc = switch_to_user("ilmari", runner)
        self.assertNotEqual(rc, 0)


class TestMain(unittest.TestCase):
    def test_no_args_exits_nonzero(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            main([])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_switches_to_given_user(self) -> None:
        runner = CapturingRunner([0])
        rc = main(["ilmari"], runner=runner)
        self.assertEqual(rc, 0)
        self.assertIn("ilmari", runner.calls[0])

    def test_uses_custom_runner(self) -> None:
        runner = CapturingRunner([0])
        main(["tapiiri"], runner=runner)
        self.assertEqual(len(runner.calls), 1)


if __name__ == "__main__":
    unittest.main()
