from __future__ import annotations

import sys
from typing import Sequence

from scripts_py.ensure_password_manager_login import main as _pm_main
from scripts_py.password_manager import CheckResult, get_password_manager_backend
from scripts_py.utils import log_error


def check_lpass_logged_in() -> CheckResult:
    return get_password_manager_backend("lastpass").check_logged_in()


def ensure_lpass_logged_in_or_exit(*, err, out) -> None:
    res = check_lpass_logged_in()
    if res.ok:
        return

    backend = get_password_manager_backend("lastpass")
    log_error(backend.format_help_message(hint=res.hint), err=err)
    raise SystemExit(1)


def warn_if_lpass_not_logged_in(*, err) -> None:
    res = check_lpass_logged_in()
    if res.ok:
        return

    backend = get_password_manager_backend("lastpass")
    print(f"[WARN] {backend.format_help_message(hint=res.hint)}", file=err)


def main(argv: Sequence[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # Compatibility entrypoint: always use the LastPass backend.
    return int(_pm_main(["--provider", "lastpass", *list(argv)]))
