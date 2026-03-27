from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Protocol, Sequence


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
    return ["loginctl", "list-sessions", "--no-legend"]


def build_activate_argv(session_id: str) -> list[str]:
    return ["loginctl", "activate", session_id]


def build_lock_argv() -> list[str]:
    return ["loginctl", "lock-session"]


def parse_sessions_output(output: str, target_user: str) -> str | None:
    """Return the first session ID for target_user from loginctl list-sessions output.

    loginctl list-sessions --no-legend format:
      SESSION  UID  USER     SEAT   TTY
      3        1001 ilmari   seat0
    """
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[2] == target_user:
            return parts[0]
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
