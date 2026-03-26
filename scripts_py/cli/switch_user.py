from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Protocol, Sequence


class SubprocessRunner(Protocol):
    def run(self, argv: Sequence[str]) -> int:  # pragma: no cover
        ...


class DefaultRunner:
    def run(self, argv: Sequence[str]) -> int:
        return subprocess.run(list(argv)).returncode


def build_gdbus_argv(target_user: str) -> list[str]:
    return [
        "gdbus",
        "call",
        "--system",
        "--dest",
        "org.gnome.DisplayManager",
        "--object-path",
        "/org/gnome/DisplayManager/Manager",
        "--method",
        "org.gnome.DisplayManager.Manager.SwitchToUser",
        target_user,
        "",
    ]


def build_lock_argv() -> list[str]:
    return ["loginctl", "lock-session"]


def switch_to_user(target_user: str, runner: SubprocessRunner) -> int:
    """Ask GDM to switch to target_user.

    First tries the D-Bus SwitchToUser method directly. If that fails
    (e.g. running in a non-GDM session or insufficient D-Bus access),
    falls back to locking the current session so GDM shows the user
    switcher screen.
    """
    rc = runner.run(build_gdbus_argv(target_user))
    if rc == 0:
        return 0
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
