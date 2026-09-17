from __future__ import annotations

import json
import unittest
from collections.abc import Sequence

from scripts_py.cli.switch_user import (
    build_activate_argv,
    build_list_sessions_argv,
    build_lock_argv,
    main,
    parse_sessions_output,
    switch_to_user,
)


def _session(
    session: str,
    uid: int,
    user: str,
    seat: str | None = "seat0",
    klass: str = "user",
    tty: str | None = "tty1",
) -> dict[str, object]:
    return {
        "session": session,
        "uid": uid,
        "user": user,
        "seat": seat,
        "leader": 1000 + int(session),
        "class": klass,
        "tty": tty,
        "idle": False,
        "since": None,
    }


def _sessions_json(*sessions: dict[str, object]) -> str:
    return json.dumps(list(sessions))


SAMPLE_SESSIONS = _sessions_json(
    _session("3", 1001, "ilmari", tty="tty3"),
    _session("2", 1000, "tapiiri", tty="tty2"),
)


class CapturingRunner:
    """Test double that records calls and returns pre-configured values."""

    def __init__(
        self,
        return_codes: list[int] | None = None,
        outputs: list[tuple[int, str]] | None = None,
    ) -> None:
        self._codes = iter(return_codes or [])
        self._outputs = iter(outputs or [])
        self.calls: list[list[str]] = []
        self.output_calls: list[list[str]] = []

    def run(self, argv: Sequence[str]) -> int:
        self.calls.append(list(argv))
        return next(self._codes)

    def run_output(self, argv: Sequence[str]) -> tuple[int, str]:
        self.output_calls.append(list(argv))
        return next(self._outputs)


class TestBuildArgvHelpers(unittest.TestCase):
    def test_list_sessions_uses_loginctl(self) -> None:
        self.assertEqual(build_list_sessions_argv()[0], "loginctl")
        self.assertIn("list-sessions", build_list_sessions_argv())

    def test_activate_uses_loginctl(self) -> None:
        argv = build_activate_argv("42")
        self.assertEqual(argv[0], "loginctl")
        self.assertIn("activate", argv)
        self.assertIn("42", argv)

    def test_lock_uses_loginctl(self) -> None:
        argv = build_lock_argv()
        self.assertEqual(argv[0], "loginctl")
        self.assertIn("lock-session", argv)


class TestParseSessionsOutput(unittest.TestCase):
    def test_finds_session_id_for_user(self) -> None:
        self.assertEqual(parse_sessions_output(SAMPLE_SESSIONS, "ilmari"), "3")

    def test_finds_session_id_for_other_user(self) -> None:
        self.assertEqual(parse_sessions_output(SAMPLE_SESSIONS, "tapiiri"), "2")

    def test_returns_none_for_unknown_user(self) -> None:
        self.assertIsNone(parse_sessions_output(SAMPLE_SESSIONS, "nobody"))

    def test_empty_output_returns_none(self) -> None:
        self.assertIsNone(parse_sessions_output("", "ilmari"))

    def test_returns_first_session_when_multiple(self) -> None:
        output = _sessions_json(
            _session("5", 1001, "ilmari", tty="tty5"),
            _session("6", 1001, "ilmari", seat="seat1", tty="tty6"),
        )
        self.assertEqual(parse_sessions_output(output, "ilmari"), "5")

    def test_no_partial_username_match(self) -> None:
        self.assertIsNone(parse_sessions_output(SAMPLE_SESSIONS, "ilmar"))

    def test_skips_seatless_manager_session(self) -> None:
        """systemd lists the seatless user@<uid>.service manager session first
        when its ID sorts below the graphical one; activating it fails."""
        output = _sessions_json(
            _session("10", 1002, "ilmari-offeri", seat=None, klass="manager", tty=None),
            _session("12", 1002, "ilmari-offeri", tty="tty2"),
        )
        self.assertEqual(parse_sessions_output(output, "ilmari-offeri"), "12")

    def test_seatless_only_returns_none(self) -> None:
        output = _sessions_json(
            _session("10", 1002, "ilmari-offeri", seat=None, klass="manager", tty=None),
        )
        self.assertIsNone(parse_sessions_output(output, "ilmari-offeri"))

    def test_malformed_json_returns_none(self) -> None:
        self.assertIsNone(parse_sessions_output("not json at all", "ilmari"))


class TestSwitchToUser(unittest.TestCase):
    def test_activates_existing_session_directly(self) -> None:
        runner = CapturingRunner(return_codes=[0], outputs=[(0, SAMPLE_SESSIONS)])
        rc = switch_to_user("ilmari", runner)
        self.assertEqual(rc, 0)
        self.assertEqual(len(runner.calls), 1)
        self.assertIn("activate", runner.calls[0])
        self.assertIn("3", runner.calls[0])

    def test_does_not_lock_when_session_found(self) -> None:
        runner = CapturingRunner(return_codes=[0], outputs=[(0, SAMPLE_SESSIONS)])
        switch_to_user("ilmari", runner)
        self.assertNotIn("lock-session", runner.calls[0])

    def test_locks_when_no_session_found(self) -> None:
        output = _sessions_json(_session("2", 1000, "tapiiri"))
        runner = CapturingRunner(return_codes=[0], outputs=[(0, output)])
        switch_to_user("ilmari", runner)
        self.assertIn("lock-session", runner.calls[0])

    def test_returns_activate_exit_code(self) -> None:
        runner = CapturingRunner(return_codes=[42], outputs=[(0, SAMPLE_SESSIONS)])
        self.assertEqual(switch_to_user("ilmari", runner), 42)

    def test_returns_lock_exit_code(self) -> None:
        runner = CapturingRunner(return_codes=[1], outputs=[(0, "")])
        self.assertEqual(switch_to_user("ilmari", runner), 1)

    def test_queries_list_sessions_first(self) -> None:
        runner = CapturingRunner(return_codes=[0], outputs=[(0, SAMPLE_SESSIONS)])
        switch_to_user("ilmari", runner)
        self.assertIn("list-sessions", runner.output_calls[0])


class TestMain(unittest.TestCase):
    def test_no_args_exits_nonzero(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            main([])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_switches_to_given_user(self) -> None:
        runner = CapturingRunner(return_codes=[0], outputs=[(0, SAMPLE_SESSIONS)])
        rc = main(["ilmari"], runner=runner)
        self.assertEqual(rc, 0)

    def test_uses_custom_runner(self) -> None:
        runner = CapturingRunner(return_codes=[0], outputs=[(0, SAMPLE_SESSIONS)])
        main(["ilmari"], runner=runner)
        self.assertEqual(len(runner.output_calls), 1)


if __name__ == "__main__":
    unittest.main()
