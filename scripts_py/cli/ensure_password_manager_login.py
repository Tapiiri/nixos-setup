from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import NoReturn, Sequence

from scripts_py.lib.password_manager import get_password_manager_backend
from scripts_py.lib.utils import OsExecRunner, Runner, log_error, log_info


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name,
        description=(
            "Ensure password manager CLI is logged in (for secretspec), "
            "optionally exec a command.\n\n"
            "Provider selection:\n"
            "- Default provider comes from $NIXOS_SETUP_PASSWORD_MANAGER (defaults to 'lastpass')\n"
            "- You can override for a single invocation with --provider\n\n"
            "Examples:\n"
            "  ensure-password-manager-login --check\n"
            "  ensure-password-manager-login -- devenv tasks run check:all"
        ),
        add_help=True,
    )
    p.add_argument(
        "--provider",
        default=None,
        help="Password manager provider id (default: $NIXOS_SETUP_PASSWORD_MANAGER or 'lastpass')",
    )
    p.add_argument(
        "--check",
        action="store_true",
        help="Only check and exit 0/1; do not exec any command",
    )
    p.add_argument(
        "--warn-only",
        action="store_true",
        help="If not logged in, print a warning but exit 0",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="When --check succeeds (or no command is provided), print nothing",
    )
    p.add_argument(
        "cmd",
        nargs=argparse.REMAINDER,
        help="Command to exec, preceded by -- (e.g. -- devenv tasks run ...) ",
    )
    return p.parse_args(list(argv))


def _exec_cmd(cmd: Sequence[str], *, runner: Runner) -> NoReturn:
    if not cmd:
        raise SystemExit(2)

    if cmd[0] == "--":
        cmd = cmd[1:]

    if not cmd:
        raise SystemExit(2)

    runner.exec(cmd)


def _ensure_logged_in_or_exit(*, provider: str | None, err) -> None:
    backend = get_password_manager_backend(provider)
    res = backend.check_logged_in()
    if res.ok:
        return

    msg = backend.format_help_message(hint=res.hint)
    log_error(msg, err=err)
    raise SystemExit(1)


def _warn_if_not_logged_in(*, provider: str | None, err) -> None:
    backend = get_password_manager_backend(provider)
    res = backend.check_logged_in()
    if res.ok:
        return

    msg = backend.format_help_message(hint=res.hint)
    print(f"[WARN] {msg}", file=err)


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    args = parse_args(argv)

    if args.warn_only:
        _warn_if_not_logged_in(provider=args.provider, err=sys.stderr)
        return 0

    _ensure_logged_in_or_exit(provider=args.provider, err=sys.stderr)

    if args.check:
        if not args.quiet:
            log_info("Password manager is logged in", out=sys.stdout)
        return 0

    if args.cmd:
        _exec_cmd(args.cmd, runner=OsExecRunner())

    if not args.quiet:
        log_info("Password manager is logged in", out=sys.stdout)
    return 0
