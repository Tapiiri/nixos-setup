from __future__ import annotations

import argparse
import json
import pwd
import subprocess
import sys
from typing import Any, Callable, Protocol, Sequence, cast

GDM_BUS_NAME = "org.gnome.DisplayManager"
GDM_FACTORY_PATH = "/org/gnome/DisplayManager/LocalDisplayFactory"
GDM_FACTORY_IFACE = "org.gnome.DisplayManager.LocalDisplayFactory"


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


def build_greeter_argv() -> list[str]:
    """Build the argv that asks GDM to open a login screen on a spare VT.

    `CreateTransientDisplay` is what gnome-shell's own "Switch User" item calls
    (via libgdm's `gdm_goto_login_session`). GDM's D-Bus policy allows it for
    every user -- unlike the neighbouring factory methods, which are restricted
    to root and the `gdm` group -- so no sudo or polkit agent is involved.
    """
    return [
        "busctl",
        "call",
        "--system",
        GDM_BUS_NAME,
        GDM_FACTORY_PATH,
        GDM_FACTORY_IFACE,
        "CreateTransientDisplay",
    ]


def _parse_sessions(output: str) -> list[dict[str, Any]]:
    try:
        parsed: object = json.loads(output)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [cast(dict[str, Any], e) for e in cast(list[Any], parsed) if isinstance(e, dict)]


def _activatable_session_id(session: dict[str, Any]) -> str | None:
    """Return the session's ID if loginctl can activate it, else None.

    Only sessions attached to a seat can be activated. systemd lists a seatless
    `manager` session per logged-in user (their `user@<uid>.service`) alongside
    the real graphical one, and `loginctl activate` on a seatless session fails
    with "Operation not supported". Session IDs are not ordered such that the
    graphical one comes first, so the seat must be checked rather than assumed.
    """
    if not session.get("seat"):
        return None
    session_id: object = session.get("session")
    return None if session_id is None else str(session_id)


def parse_sessions_output(output: str, target_user: str) -> str | None:
    """Return target_user's activatable session ID from loginctl JSON output."""
    for session in _parse_sessions(output):
        if session.get("user") != target_user:
            continue
        found = _activatable_session_id(session)
        if found is not None:
            return found
    return None


def parse_greeter_session(output: str) -> str | None:
    """Return the ID of an already-running GDM greeter, if there is one.

    A greeter left over from an earlier switch is reused instead of asking GDM
    for another one, so repeated `switch-user` calls do not pile up VTs.
    """
    for session in _parse_sessions(output):
        if session.get("class") != "greeter":
            continue
        found = _activatable_session_id(session)
        if found is not None:
            return found
    return None


def user_exists(name: str) -> bool:
    try:
        pwd.getpwnam(name)
    except KeyError:
        return False
    return True


def open_login_screen(runner: SubprocessRunner, output: str, *, lock: bool) -> int:
    """Show a GDM login screen so the target user can log in.

    Reuses a running greeter when one exists, otherwise asks GDM for a
    transient display. `loginctl lock-session` is only a last resort: it locks
    the *current* session, which leaves the caller staring at their own unlock
    prompt rather than at a user list.
    """
    greeter_id = parse_greeter_session(output)
    if greeter_id is not None:
        rc = runner.run(build_activate_argv(greeter_id))
    else:
        rc, _ = runner.run_output(build_greeter_argv())
    if rc != 0:
        print(
            "Could not open a GDM login screen; locking this session instead.",
            file=sys.stderr,
        )
        return runner.run(build_lock_argv())
    if lock:
        runner.run(build_lock_argv())
    return 0


def switch_to_user(target_user: str, runner: SubprocessRunner, *, lock: bool = True) -> int:
    """Switch to target_user's session.

    If the user already has a session on a seat, activates it directly. If not,
    opens a GDM login screen on a spare VT so they can log in; the caller's own
    session keeps running in the background and is locked unless lock=False.
    """
    _, output = runner.run_output(build_list_sessions_argv())
    session_id = parse_sessions_output(output, target_user)
    if session_id is not None:
        return runner.run(build_activate_argv(session_id))
    print(
        f"No session for {target_user}; opening the login screen -- pick {target_user} there.",
        file=sys.stderr,
    )
    return open_login_screen(runner, output, lock=lock)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="switch-user",
        description="Switch to another user's GNOME session via GDM.",
    )
    p.add_argument("target_user", help="Username to switch to (e.g. ilmari, tapiiri)")
    p.add_argument(
        "--no-lock",
        dest="lock",
        action="store_false",
        help="Leave this session unlocked when opening the login screen.",
    )
    return p.parse_args(list(argv))


def main(
    argv: Sequence[str] | None = None,
    *,
    runner: SubprocessRunner | None = None,
    exists: Callable[[str], bool] | None = None,
) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if runner is None:
        runner = DefaultRunner()
    if exists is None:
        exists = user_exists
    args = parse_args(argv)
    if not exists(args.target_user):
        print(f"switch-user: no such user: {args.target_user}", file=sys.stderr)
        return 2
    return switch_to_user(args.target_user, runner, lock=args.lock)
