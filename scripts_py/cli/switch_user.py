from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any, Protocol, Sequence, cast


class SubprocessRunner(Protocol):
    def run(self, argv: Sequence[str]) -> int:  # pragma: no cover
        ...

    def run_output(self, argv: Sequence[str]) -> tuple[int, str]:  # pragma: no cover
        ...


class DefaultRunner:
    def run(self, argv: Sequence[str]) -> int:
        return subprocess.run(list(argv)).returncode

    def run_output(self, argv: Sequence[str]) -> tuple[int, str]:
        result = subprocess.run(list(argv), capture_output=True, text=True)
        return result.returncode, result.stdout


def build_list_sessions_argv() -> list[str]:
    return ["loginctl", "list-sessions", "--json=short"]


def build_activate_argv(session_id: str) -> list[str]:
    return ["loginctl", "activate", session_id]


def build_lock_argv() -> list[str]:
    return ["loginctl", "lock-session"]


def parse_sessions_output(output: str, target_user: str) -> str | None:
    """Return target_user's activatable session ID from loginctl JSON output.

    Only sessions attached to a seat can be activated. systemd lists a seatless
    `manager` session per logged-in user (their `user@<uid>.service`) alongside
    the real graphical one, and `loginctl activate` on a seatless session fails
    with "Operation not supported". Session IDs are not ordered such that the
    graphical one comes first, so the seat must be checked rather than assumed.
    """
    try:
        parsed: object = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, list):
        return None
    for entry in cast(list[Any], parsed):
        if not isinstance(entry, dict):
            continue
        session = cast(dict[str, Any], entry)
        if session.get("user") != target_user:
            continue
        if not session.get("seat"):
            continue
        session_id: object = session.get("session")
        if session_id is not None:
            return str(session_id)
    return None


def switch_to_user(target_user: str, runner: SubprocessRunner) -> int:
    """Switch to target_user's session.

    If the user already has an active session, activates it directly via
    loginctl. Otherwise locks the current session so GDM shows the user
    switcher screen.
    """
    _, output = runner.run_output(build_list_sessions_argv())
    session_id = parse_sessions_output(output, target_user)
    if session_id is not None:
        return runner.run(build_activate_argv(session_id))
    return runner.run(build_lock_argv())


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="switch-user",
        description="Switch to another user's GNOME session via GDM.",
    )
    p.add_argument("target_user", help="Username to switch to (e.g. ilmari, tapiiri)")
    return p.parse_args(list(argv))


def main(argv: Sequence[str] | None = None, *, runner: SubprocessRunner | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if runner is None:
        runner = DefaultRunner()
    args = parse_args(argv)
    return switch_to_user(args.target_user, runner)
