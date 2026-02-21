from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn, Sequence

from scripts_py.utils import OsExecRunner, Runner, log_error, log_info


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    hint: str | None = None


def _run_lpass_status(lpass_path: str) -> CheckResult:
    try:
        cp = subprocess.run([lpass_path, "status"], capture_output=True, text=True)
    except OSError as e:
        return CheckResult(ok=False, hint=str(e))

    if cp.returncode == 0:
        return CheckResult(ok=True)

    hint = (cp.stderr or "").strip() or (cp.stdout or "").strip() or None
    return CheckResult(ok=False, hint=hint)


def check_lpass_logged_in() -> CheckResult:
    lpass_path = shutil.which("lpass")
    if not lpass_path:
        return CheckResult(
            ok=False,
            hint=(
                "lpass executable not found on PATH. secretspec is enabled in this repo and "
                "will try to use LastPass CLI to provide secrets. Install lastpass-cli (lpass) "
                "and log in."
            ),
        )

    return _run_lpass_status(lpass_path)


def _format_help_message(*, hint: str | None) -> str:
    details = f"\n\nDetails: {hint}" if hint else ""
    return (
        "LastPass CLI is not authenticated (lpass is not logged in).\n"
        "This repo enables devenv+secretspec, which uses lpass to provide required secrets.\n\n"
        "Fix: run `lpass login <email>` (and complete 2FA if prompted).\n"
        "Then retry (for direnv: `direnv reload`; for pre-commit: re-run the git command)."
        f"{details}"
    )


def ensure_lpass_logged_in_or_exit(*, err, out) -> None:
    res = check_lpass_logged_in()
    if res.ok:
        return

    msg = _format_help_message(hint=res.hint)
    log_error(msg, err=err)
    raise SystemExit(1)


def warn_if_lpass_not_logged_in(*, err) -> None:
    """Print a helpful warning but do not fail.

    Intended for interactive shell entry hooks.
    """

    res = check_lpass_logged_in()
    if res.ok:
        return

    msg = _format_help_message(hint=res.hint)
    # Keep it as a warning so shells don't look "broken".
    print(f"[WARN] {msg}", file=err)


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog=Path(sys.argv[0]).name,
        description=(
            "Ensure LastPass CLI is logged in (for secretspec), optionally exec a command.\n\n"
            "Examples:\n"
            "  ensure-lpass-login --check\n"
            "  ensure-lpass-login -- devenv tasks run check:all"
        ),
        add_help=True,
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
        help="When --check succeeds, print nothing",
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


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    args = parse_args(argv)

    if args.warn_only:
        warn_if_lpass_not_logged_in(err=sys.stderr)
        return 0

    # Always fail fast with an actionable message.
    ensure_lpass_logged_in_or_exit(err=sys.stderr, out=sys.stdout)

    if args.check:
        if not args.quiet:
            log_info("lpass is logged in", out=sys.stdout)
        return 0

    if args.cmd:
        _exec_cmd(args.cmd, runner=OsExecRunner())

    # No command provided: treat as a plain check.
    if not args.quiet:
        log_info("lpass is logged in", out=sys.stdout)
    return 0
